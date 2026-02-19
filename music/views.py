"""
Spotify-style UI - Compact + Pause/Resume + Source Info
"""

import discord
import wavelink
from discord.ui import View, Button
import logging
from music.lyrics import fetch_lyrics, clean_title, clean_artist

log = logging.getLogger(__name__)

def format_time(ms: int) -> str:
    seconds = ms // 1000
    mins, secs = divmod(seconds, 60)
    if mins >= 60:
        hours, mins = divmod(mins, 60)
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

def get_source_info(uri: str) -> tuple:
    """Return (emoji, name) based on track source"""
    uri = str(uri or "").lower()
    if "youtube" in uri or "youtu.be" in uri:
        return "▶️", "YouTube"
    elif "spotify" in uri:
        return "🎧", "Spotify"
    elif "soundcloud" in uri:
        return "☁️", "SoundCloud"
    elif "deezer" in uri:
        return "🎶", "Deezer"
    elif "apple" in uri:
        return "🍎", "Apple Music"
    elif "tidal" in uri:
        return "🌊", "Tidal"
    elif "bandcamp" in uri:
        return "🎸", "Bandcamp"
    elif "nicovideo" in uri:
        return "📺", "NicoNico"
    elif "twitch" in uri:
        return "💜", "Twitch"
    elif "reddit" in uri:
        return "🤖", "Reddit"
    elif "vimeo" in uri:
        return "🎬", "Vimeo"
    elif "tiktok" in uri:
        return "🎵", "TikTok"
    elif "mixcloud" in uri:
        return "🎛️", "Mixcloud"
    elif "yandex" in uri:
        return "🔴", "Yandex Music"
    return "🎵", "Stream"

def create_now_playing_embed(track: wavelink.Playable, player) -> discord.Embed:
    """Compact Spotify-style embed with source & requester"""
    
    # Progress bar
    try:
        duration = track.length
        position = player.position if hasattr(player, 'position') else 0
        bar_len = 10
        filled = max(0, min(bar_len, int((position / duration) * bar_len))) if duration > 0 else 0
        bar = "▬" * filled + "🔘" + "▬" * (bar_len - filled)
        progress = f"`{format_time(position)}` {bar} `{format_time(duration)}`"
    except:
        progress = "`--:--` ▬▬▬🔘▬▬▬▬▬▬ `--:--`"
    
    # Source info
    src_emoji, src_name = get_source_info(track.uri)
    
    # Paused indicator
    paused = " ⏸️" if player.paused else ""
    
    # Title (truncate if too long)
    title = track.title[:50] + "..." if len(track.title) > 50 else track.title
    
    # Build embed
    embed = discord.Embed(color=0x1DB954)
    embed.description = (
        f"**🎵 Now Playing{paused}**\n\n"
        f"**[{title}]({track.uri})**\n"
        f"👤 {track.author}\n\n"
        f"{progress}\n\n"
        f"{src_emoji} **{src_name}**"
    )
    
    # Thumbnail
    if track.artwork:
        embed.set_thumbnail(url=track.artwork)
    
    # Status footer
    from music.player import get_player
    mp = get_player(player.guild.id)
    
    status = []
    if mp:
        loop_icons = {"off": "➡️ Off", "track": "🔂 Track", "queue": "🔁 Queue"}
        status.append(loop_icons.get(mp.loop_mode, "➡️ Off"))
        if mp.shuffle_enabled: status.append("🔀 Shuffle")
        q = len(mp.queue)
        if q > 0: status.append(f"📋 {q} in queue")
    status.append(f"🔊 {player.volume}%")
    
    embed.set_footer(text=" • ".join(status))
    
    # Requester (show avatar + name)
    if hasattr(track, 'requester') and track.requester:
        embed.set_author(
            name=f"🎧 {track.requester.display_name}",
            icon_url=track.requester.display_avatar.url
        )
    
    return embed

async def update_now_playing(player: wavelink.Player, track: wavelink.Playable):
    """Update the now playing message"""
    from music.player import get_player
    mp = get_player(player.guild.id)
    if mp and mp.now_playing_message:
        try:
            embed = create_now_playing_embed(track, player)
            view = MusicControlView(player)
            await mp.now_playing_message.edit(embed=embed, view=view)
        except Exception as e:
            log.debug(f"Could not update NP: {e}")

class MusicControlView(View):
    """Control buttons with separate Pause & Resume"""
    
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)
        self.player = player
        from music.player import get_player
        self.music_player = get_player(player.guild.id)
    
    # Row 1: Transport controls
    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, custom_id="music:prev", row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: Button):
        if not self.music_player:
            return await interaction.response.send_message("❌ No player!", ephemeral=True)
        track = await self.music_player.play_previous()
        if track:
            await interaction.response.send_message(f"⏮️ **{track.title}**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No previous!", ephemeral=True)
    
    @discord.ui.button(emoji="⏸️", label="Pause", style=discord.ButtonStyle.primary, custom_id="music:pause", row=0)
    async def pause_btn(self, interaction: discord.Interaction, button: Button):
        if not self.player.playing:
            return await interaction.response.send_message("❌ Nothing playing!", ephemeral=True)
        if self.player.paused:
            return await interaction.response.send_message("⚠️ Already paused!", ephemeral=True)
        await self.player.pause(True)
        # Update embed to show paused state
        if self.player.current:
            embed = create_now_playing_embed(self.player.current, self.player)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("⏸️ Paused!", ephemeral=True)
    
    @discord.ui.button(emoji="▶️", label="Resume", style=discord.ButtonStyle.success, custom_id="music:resume", row=0)
    async def resume_btn(self, interaction: discord.Interaction, button: Button):
        if not self.player.paused:
            return await interaction.response.send_message("⚠️ Not paused!", ephemeral=True)
        await self.player.pause(False)
        # Update embed to remove paused state
        if self.player.current:
            embed = create_now_playing_embed(self.player.current, self.player)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("▶️ Resumed!", ephemeral=True)
    
    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="music:skip", row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: Button):
        if not self.music_player:
            return await interaction.response.send_message("❌ No player!", ephemeral=True)
        current = self.player.current
        await self.music_player.skip()
        name = current.title if current else ""
        await interaction.response.send_message(f"⏭️ Skipped: **{name}**", ephemeral=True)
    
    # Row 2: Mode controls
    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="music:loop", row=1)
    async def loop_btn(self, interaction: discord.Interaction, button: Button):
        if not self.music_player:
            return await interaction.response.send_message("❌ No player!", ephemeral=True)
        mode = await self.music_player.toggle_loop()
        icons = {"off": "Off ➡️", "track": "Track 🔂", "queue": "Queue 🔁"}
        await interaction.response.send_message(f"🔁 Loop: **{icons[mode]}**", ephemeral=True)
    
    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music:shuf", row=1)
    async def shuffle_btn(self, interaction: discord.Interaction, button: Button):
        if not self.music_player:
            return await interaction.response.send_message("❌ No player!", ephemeral=True)
        on = await self.music_player.toggle_shuffle()
        await interaction.response.send_message(f"🔀 Shuffle: **{'On' if on else 'Off'}**", ephemeral=True)
    
    @discord.ui.button(emoji="📋", label="Queue", style=discord.ButtonStyle.secondary, custom_id="music:queue", row=1)
    async def queue_btn(self, interaction: discord.Interaction, button: Button):
        if not self.music_player:
            return await interaction.response.send_message("❌ No player!", ephemeral=True)
        lines = self.music_player.get_queue_display(8)
        total = sum(t.length for t in self.music_player.queue)
        embed = discord.Embed(
            title=f"📋 Queue ({len(self.music_player.queue)})",
            description="\n".join(lines),
            color=0x1DB954
        )
        embed.set_footer(text=f"Total: {format_time(total)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(emoji="📝", label="Lyrics", style=discord.ButtonStyle.secondary, custom_id="music:lyrics", row=1)
    async def lyrics_btn(self, interaction: discord.Interaction, button: Button):
        if not self.player.current:
            return await interaction.response.send_message("❌ No track!", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        track = self.player.current
        lyrics = await fetch_lyrics(title=track.title, artist=track.author, duration_ms=track.length)
        if lyrics:
            if len(lyrics) > 4000:
                lyrics = lyrics[:4000] + "\n\n*...terpotong*"
            embed = discord.Embed(
                title=f"📝 {track.title[:40]}",
                description=lyrics,
                color=0x1DB954
            )
            embed.set_footer(text=f"Artist: {track.author}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Lirik tidak ditemukan\n💡 Coba: `.lyrics {track.title}`", ephemeral=True)
    
    # Row 3: Actions
    @discord.ui.button(emoji="❤️", label="Save", style=discord.ButtonStyle.secondary, custom_id="music:fav", row=2)
    async def fav_btn(self, interaction: discord.Interaction, button: Button):
        if not self.player.current:
            return await interaction.response.send_message("❌ No track!", ephemeral=True)
        from music.favorites import FavoritesManager
        fav = FavoritesManager()
        t = self.player.current
        ok = await fav.add_favorite(interaction.user.id, t.uri, t.title, t.author)
        if ok:
            await interaction.response.send_message(f"❤️ **{t.title}** saved to favorites!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Already in favorites!", ephemeral=True)
    
    @discord.ui.button(emoji="⏹️", label="Stop", style=discord.ButtonStyle.danger, custom_id="music:stop", row=2)
    async def stop_btn(self, interaction: discord.Interaction, button: Button):
        if self.music_player:
            await self.music_player.clear_queue()
        await self.player.disconnect()
        from music.player import remove_player
        remove_player(self.player.guild.id)
        await interaction.response.send_message("⏹️ Stopped & disconnected!", ephemeral=True)
