"""
Background Scheduler for Reminders
Runs as asyncio task, checks every 30 seconds
"""
import asyncio
import logging
import discord
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from discord import Client

log = logging.getLogger(__name__)

class ReminderScheduler:
    def __init__(self, bot: "Client"):
        self.bot = bot
        self.running = False
        self.check_interval = 30
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the scheduler background task"""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info("⏰ Reminder scheduler started (interval: 30s)")
    
    async def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("⏰ Reminder scheduler stopped")
    
    async def _run_loop(self):
        """Main scheduler loop"""
        await asyncio.sleep(5)  # Wait for bot to fully start
        while self.running:
            try:
                await self._check_and_execute()
            except Exception as e:
                log.error(f"⏰ Scheduler error: {e}")
            await asyncio.sleep(self.check_interval)
    
    async def _check_and_execute(self):
        """Check for due reminders and execute them"""
        from core.database import get_due_reminders, mark_reminder_triggered
        
        due_reminders = get_due_reminders()
        
        for reminder in due_reminders:
            try:
                await self._execute_reminder(reminder)
                is_recurring = reminder["trigger_type"] in ("daily", "weekly")
                mark_reminder_triggered(reminder["id"], reschedule=is_recurring)
                log.info(f"⏰ Reminder #{reminder['id']} executed: {reminder['message'][:30]}")
            except Exception as e:
                log.error(f"⏰ Failed to execute reminder #{reminder['id']}: {e}")
                # Still mark as triggered to avoid infinite loop
                mark_reminder_triggered(reminder["id"], reschedule=False)
    
    async def _execute_reminder(self, reminder: dict):
        """Execute all actions for a reminder"""
        guild = self.bot.get_guild(reminder["guild_id"])
        if not guild:
            log.warning(f"⏰ Guild {reminder['guild_id']} not found")
            return
        
        channel = guild.get_channel(reminder["channel_id"])
        creator = guild.get_member(reminder["user_id"])
        
        # Determine target user (who gets the reminder)
        target_user_id = reminder.get("target_user_id")
        target_user_name = reminder.get("target_user_name")
        target_user = None
        
        if target_user_id:
            target_user = guild.get_member(target_user_id)
        
        if not target_user and target_user_name:
            # Search by display name
            for m in guild.members:
                if m.display_name.lower() == target_user_name.lower() or m.name.lower() == target_user_name.lower():
                    target_user = m
                    break
            # Partial match
            if not target_user:
                for m in guild.members:
                    if target_user_name.lower() in m.display_name.lower() or target_user_name.lower() in m.name.lower():
                        target_user = m
                        break
        
        # Fallback to creator if no target specified
        if not target_user:
            target_user = creator
        
        if not target_user:
            log.warning(f"⏰ No user found for reminder #{reminder['id']}")
            return
        
        actions = reminder.get("actions", [])
        message = reminder["message"]
        
        log.info(f"⏰ Executing reminder #{reminder['id']} for {target_user.display_name} (creator: {creator.display_name if creator else '?'})")
        
        # Default: mention in original channel
        if channel:
            try:
                embed = discord.Embed(
                    title="⏰ Reminder!",
                    description=message,
                    color=0xFF6B6B,
                    timestamp=datetime.now()
                )
                creator_name = creator.display_name if creator else "Someone"
                if target_user != creator:
                    embed.set_footer(text=f"Reminder dari {creator_name} untuk {target_user.display_name}")
                else:
                    embed.set_footer(text=f"Reminder untuk {target_user.display_name}")
                await channel.send(f"{target_user.mention}", embed=embed)
            except Exception as e:
                log.error(f"⏰ Failed to send channel reminder: {e}")
        
        # Execute additional actions (pass target_user instead of creator)
        for action in actions:
            try:
                await self._execute_action(action, guild, channel, target_user, message)
            except Exception as e:
                log.error(f"⏰ Action error: {e}")
    
    async def _execute_action(self, action: dict, guild, channel, user, message: str):
        """Execute a single reminder action"""
        action_type = action.get("type", "")
        
        # ── DM User ──
        if action_type == "dm":
            try:
                dm_channel = await user.create_dm()
                dm_message = action.get("message") or f"⏰ **Reminder:** {message}"
                
                embed = discord.Embed(
                    title="⏰ Reminder",
                    description=dm_message,
                    color=0xFF6B6B,
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"From server: {guild.name}")
                
                await dm_channel.send(embed=embed)
                log.info(f"⏰ DM sent to {user.display_name}")
            except discord.Forbidden:
                log.warning(f"⏰ Cannot DM {user.display_name} (DM closed)")
                if channel:
                    await channel.send(f"⚠️ Tidak bisa DM {user.mention} (DM tertutup)")
            except Exception as e:
                log.error(f"⏰ DM error: {e}")
        
        # ── Play Music ──
        elif action_type == "music":
            await self._execute_music_action(action, guild, channel, user)
        
        # ── Send to specific channel ──
        elif action_type == "channel_message":
            target_channel_name = action.get("channel", "")
            target_channel = discord.utils.get(guild.text_channels, name=target_channel_name)
            if target_channel:
                try:
                    msg_content = action.get("message") or f"⏰ Reminder: {message}"
                    await target_channel.send(f"{user.mention} {msg_content}")
                except Exception as e:
                    log.error(f"⏰ Channel message error: {e}")
            else:
                log.warning(f"⏰ Channel '{target_channel_name}' not found")
        
        # ── Voice Announcement (TTS - future) ──
        elif action_type == "voice_announcement":
            log.info(f"⏰ Voice announcement requested (not yet implemented): {message}")
            # Future: use gTTS + wavelink to play TTS in voice channel
    
    async def _execute_music_action(self, action: dict, guild, channel, user):
        """Execute music action"""
        try:
            import wavelink
            from music.player import MusicPlayer, get_player, set_player
        except ImportError:
            log.error("⏰ Music module not available")
            return
        
        music_action = action.get("action", "play")
        query = action.get("query", "")
        
        if music_action != "play" or not query:
            return
        
        # Check if user is in voice channel
        if not user.voice or not user.voice.channel:
            log.warning(f"⏰ User {user.display_name} not in VC for music reminder")
            if channel:
                await channel.send(f"🎵 Reminder mau play musik tapi {user.mention} tidak di voice channel!")
            return
        
        try:
            player: wavelink.Player = guild.voice_client
            
            if not player:
                player = await user.voice.channel.connect(cls=wavelink.Player)
                music_player = MusicPlayer(player)
                set_player(guild.id, music_player)
                log.info(f"⏰ Joined VC: {user.voice.channel.name}")
            else:
                music_player = get_player(guild.id)
                if not music_player:
                    music_player = MusicPlayer(player)
                    set_player(guild.id, music_player)
            
            # Search and play
            tracks = await wavelink.Playable.search(query)
            if tracks:
                if isinstance(tracks, wavelink.Playlist):
                    track = tracks.tracks[0]
                else:
                    track = tracks[0]
                
                track.requester = user
                
                if not player.playing:
                    await player.play(track)
                    if channel:
                        await channel.send(f"🎵 Reminder music: **{track.title}**")
                else:
                    await music_player.add_track(track)
                    if channel:
                        await channel.send(f"🎵 Added to queue: **{track.title}**")
                
                log.info(f"⏰ Music played: {track.title}")
            else:
                log.warning(f"⏰ No tracks found for: {query}")
                if channel:
                    await channel.send(f"❌ Tidak menemukan musik: {query}")
        
        except Exception as e:
            log.error(f"⏰ Music play error: {e}")
            if channel:
                await channel.send(f"❌ Error playing music: {e}")


# Global scheduler instance
_scheduler: Optional[ReminderScheduler] = None

def get_scheduler() -> Optional[ReminderScheduler]:
    return _scheduler

def init_scheduler(bot) -> ReminderScheduler:
    global _scheduler
    _scheduler = ReminderScheduler(bot)
    return _scheduler
