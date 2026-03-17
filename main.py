"""
Discord AI Bot - Entry Point
Multi-provider AI with fallback system
Settings persist via Turso Cloud / SQLite
"""

from typing import Dict
import aiohttp
import tempfile
import os
import discord
from discord.ext import commands
import wavelink
import asyncio
import logging
from datetime import datetime, timedelta
from skills.tts_skill import generate_tts, cleanup_old_tts, parse_speed, VOICES, VOICE_ALIASES, SPEED_PRESETS

from config import (
    DISCORD_TOKEN,
    DISCORD_PREFIX,
    DEFAULTS,
    PROVIDERS,
    list_available_providers
)
from core.database import (
    init_db,
    SettingsManager,
    USE_TURSO,
    DB_PATH,
    create_reminder,
    init_user_locations_table,
    set_user_location,
    get_user_location,
    delete_user_location
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# ============================================================
# INIT DATABASE
# ============================================================

init_db()
log.info("Database ready! (%s)", "Turso Cloud ☁️" if USE_TURSO else "SQLite Local 📁")

# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(DISCORD_PREFIX, ".", ","),
    intents=intents,
    help_command=None
)

# ============================================================
# ICONS
# ============================================================

PROVIDER_ICONS = {
    "groq": "🐆", "openrouter": "🧭", "pollinations": "🐝",
    "gemini": "🔷", "cloudflare": "☁️", "huggingface": "🤗",
    "cerebras": "🧠", "cohere": "🧵", "siliconflow": "🧪",
    "routeway": "🛣️", "mlvoca": "🦙", "puter": "☁️",
}

SEARCH_ICONS = {
    "duckduckgo": "🦆", "tavily": "🔎", "brave": "🦁",
    "serper": "📡", "jina": "💎",
}

MODE_ICONS = {"normal": "💬", "reasoning": "🧠", "search": "🔍"}

# ============================================================
# MONTH ALIASES
# ============================================================

MONTH_ALIASES = {
    "januari": 1, "january": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "maret": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "agustus": 8, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "october": 10, "oct": 10, "okt": 10,
    "november": 11, "nov": 11, "nop": 11,
    "desember": 12, "december": 12, "dec": 12, "des": 12,
}


def parse_month(value: str) -> int:
    if value is None:
        return None
    value = value.lower().strip()
    try:
        m = int(value)
        if 1 <= m <= 12:
            return m
    except ValueError:
        pass
    return MONTH_ALIASES.get(value)


# ============================================================
# SETTINGS HELPER
# ============================================================

def get_settings(guild_id: int) -> dict:
    return SettingsManager.get(guild_id)


def save_settings(guild_id: int):
    SettingsManager.save(guild_id)


def get_active_profile(guild_id: int) -> dict:
    s = get_settings(guild_id)
    mode = s["active_mode"]
    return s["profiles"][mode]


# ============================================================
# GEOCODING HELPER
# ============================================================

async def geocode_location(location: str) -> tuple:
    """Get lat/lon from location name using free Nominatim API"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://nominatim.openstreetmap.org/search"
            params = {"q": location, "format": "json", "limit": 1}
            headers = {"User-Agent": "DiscordBot/1.0"}

            async with session.get(
                url, params=params, headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        log.warning(f"Geocoding failed for '{location}': {e}")

    return None, None


# ============================================================
# MUSIC ACTION HANDLER
# ============================================================

async def execute_music_action(message: discord.Message, action: dict):
    from music.player import MusicPlayer, get_player, set_player, remove_player
    from music.views import create_now_playing_embed, MusicControlView

    act = action.get("action", "play")
    query = action.get("query", "")

    log.info(f"🎵 Executing music action: {act} | query: {query}")

    if act == "play":
        if not message.author.voice:
            return

        player: wavelink.Player = message.guild.voice_client

        if not player:
            try:
                player = await message.author.voice.channel.connect(cls=wavelink.Player)
                music_player = MusicPlayer(player)
                set_player(message.guild.id, music_player)
            except Exception as e:
                log.error(f"🎵 Failed to join voice: {e}")
                await message.channel.send(f"❌ Gagal join voice channel: {e}")
                return
        else:
            music_player = get_player(message.guild.id)
            if not music_player:
                music_player = MusicPlayer(player)
                set_player(message.guild.id, music_player)

        try:
            tracks = await wavelink.Playable.search(query)
            if not tracks:
                await message.channel.send(f"❌ Tidak menemukan: **{query}**")
                return

            if isinstance(tracks, wavelink.Playlist):
                for t in tracks.tracks:
                    t.requester = message.author
                await music_player.add_tracks(tracks.tracks)
                if not player.playing:
                    await music_player.play_next()
                embed = discord.Embed(title="📋 Playlist Added",
                    description=f"**{tracks.name}**\n{len(tracks.tracks)} tracks", color=0x1DB954)
                if tracks.artwork:
                    embed.set_thumbnail(url=tracks.artwork)
                await message.channel.send(embed=embed)
            else:
                track = tracks[0]
                track.requester = message.author
                if player.playing:
                    await music_player.add_track(track)
                    embed = discord.Embed(title="➕ Added to Queue",
                        description=f"**[{track.title}]({track.uri})**\n{track.author}", color=0x1DB954)
                    if track.artwork:
                        embed.set_thumbnail(url=track.artwork)
                    embed.add_field(name="Duration", value=MusicPlayer._format_time(track.length), inline=True)
                    embed.add_field(name="Position", value=f"#{len(music_player.queue)}", inline=True)
                    await message.channel.send(embed=embed)
                else:
                    await player.play(track)
                    embed = create_now_playing_embed(track, player)
                    view = MusicControlView(player)
                    np_msg = await message.channel.send(embed=embed, view=view)
                    music_player.now_playing_message = np_msg
        except Exception as e:
            log.error(f"🎵 Play error: {e}")
            await message.channel.send(f"❌ Error playing: {e}")

    elif act == "skip":
        from music.player import get_player
        music_player = get_player(message.guild.id)
        if music_player and music_player.is_playing:
            await music_player.skip()

    elif act == "stop":
        from music.player import get_player, remove_player
        player = message.guild.voice_client
        if player:
            music_player = get_player(message.guild.id)
            if music_player:
                await music_player.clear_queue()
            await player.disconnect()
            remove_player(message.guild.id)

    elif act == "pause":
        player = message.guild.voice_client
        if player and player.playing:
            await player.pause(True)

    elif act == "resume":
        player = message.guild.voice_client
        if player and player.paused:
            await player.pause(False)


# ============================================================
# DOWNLOAD ACTION HANDLER
# ============================================================

async def execute_download_action(message: discord.Message, action: dict):
    import shutil
    platform = action.get("platform", "unknown")
    filename = action.get("filename", "video.mp4")
    local_path = action.get("local_path", "")
    temp_dir = action.get("temp_dir", "")

    if not local_path or not os.path.exists(local_path):
        await message.channel.send("❌ Video tidak ditemukan.")
        return

    status_msg = await message.channel.send(f"⬆️ Uploading video dari **{platform.title()}**...")
    try:
        file_size = os.path.getsize(local_path)
        file_size_mb = file_size / 1_000_000
        if file_size > 25_000_000:
            await status_msg.edit(content=f"❌ Video terlalu besar ({file_size_mb:.1f} MB).")
            return
        if file_size < 1000:
            await status_msg.edit(content="❌ Download gagal — file corrupt.")
            return
        await status_msg.edit(content=f"⬆️ Uploading ({file_size_mb:.1f} MB)...")
        discord_file = discord.File(local_path, filename=filename)
        title = action.get("title", "")
        uploader = action.get("uploader", "")
        desc = f"📥 Video dari **{platform.title()}** ({file_size_mb:.1f} MB)"
        if uploader: desc += f"\n👤 {uploader}"
        if title: desc += f"\n🎬 {title}"
        await message.channel.send(content=desc, file=discord_file)
        await status_msg.delete()
    except Exception as e:
        log.error(f"📥 Upload error: {e}")
        await status_msg.edit(content=f"❌ Upload error: {str(e)[:100]}")
    finally:
        try:
            if os.path.exists(local_path): os.unlink(local_path)
            if temp_dir and os.path.exists(temp_dir): shutil.rmtree(temp_dir, ignore_errors=True)
        except: pass


# ============================================================
# IMAGE ACTION HANDLER
# ============================================================

async def execute_image_action(message: discord.Message, action: dict):
    image_url = action.get("image_url", "")
    if not image_url: return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    temp_dir = tempfile.mkdtemp()
                    temp_path = os.path.join(temp_dir, "generated.png")
                    with open(temp_path, "wb") as f: f.write(image_data)
                    discord_file = discord.File(temp_path, filename="generated.png")
                    await message.channel.send(file=discord_file)
                    os.unlink(temp_path)
                    os.rmdir(temp_dir)
                else:
                    embed = discord.Embed(color=0x1DB954)
                    embed.set_image(url=image_url)
                    await message.channel.send(embed=embed)
    except Exception as e:
        log.error(f"🖼️ Image error: {e}")
        embed = discord.Embed(color=0x1DB954)
        embed.set_image(url=image_url)
        await message.channel.send(embed=embed)


# ============================================================
# FILE UPLOAD ACTION HANDLER
# ============================================================

async def execute_file_upload_action(message: discord.Message, action: dict):
    local_path = action.get("local_path", "")
    filename = action.get("filename", "document")
    temp_dir = action.get("temp_dir", "")
    if not local_path or not os.path.exists(local_path): return
    try:
        file_size = os.path.getsize(local_path)
        if file_size > 25_000_000:
            await message.channel.send(f"❌ File terlalu besar ({file_size / 1_000_000:.1f} MB)")
            return
        discord_file = discord.File(local_path, filename=filename)
        await message.channel.send(content=f"📎 **{filename}**", file=discord_file)
    except Exception as e:
        log.error(f"📄 File upload error: {e}")
    finally:
        try:
            if os.path.exists(local_path): os.unlink(local_path)
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except: pass


# ============================================================
# REMINDER ACTION HANDLER — 100% Database Persistent
# ============================================================

async def execute_reminder_action(message: discord.Message, action: dict):
    reminder_msg = action.get("message", "⏰ Reminder!")
    minutes = action.get("trigger_minutes")
    daily_time = action.get("daily_time")
    recurring = action.get("recurring", False)
    timezone = action.get("timezone", "Asia/Jakarta")

    try:
        if minutes:
            reminder_id = create_reminder(
                guild_id=message.guild.id, channel_id=message.channel.id,
                user_id=message.author.id, user_name=message.author.display_name,
                message=reminder_msg, trigger_type="minutes",
                trigger_minutes=int(minutes), timezone=timezone,
                actions=[{"type": "channel_message"}]
            )
            await message.channel.send(
                f"⏰ Reminder tersimpan! ID: **#{reminder_id}**\n"
                f"Trigger dalam **{minutes} menit**\n💾 Persistent"
            )
        elif daily_time:
            trigger_type = "daily" if recurring else "once"
            reminder_id = create_reminder(
                guild_id=message.guild.id, channel_id=message.channel.id,
                user_id=message.author.id, user_name=message.author.display_name,
                message=reminder_msg, trigger_type=trigger_type,
                trigger_time=daily_time, timezone=timezone,
                actions=[{"type": "channel_message"}]
            )
            recur_text = "harian" if recurring else "sekali"
            await message.channel.send(
                f"⏰ Reminder tersimpan! ID: **#{reminder_id}**\n"
                f"Waktu: **{daily_time}** ({timezone}) — {recur_text}\n💾 Persistent"
            )
        else:
            await message.channel.send("❌ Reminder gagal: format waktu tidak valid.")
    except Exception as e:
        log.error(f"⏰ Reminder error: {e}")
        await message.channel.send(f"❌ Gagal membuat reminder: {str(e)[:150]}")


# ============================================================
# SEND MESSAGE ACTION HANDLER
# ============================================================

async def execute_send_message_action(message, action):
    destination = action.get("destination", "dm")
    channel_name = action.get("channel_name", "")
    msg_content = action.get("message", "")
    target_user_name = action.get("target_user", "")
    try:
        if destination == "dm":
            target = None
            if target_user_name:
                for m in message.guild.members:
                    if m.display_name.lower() == target_user_name.lower() or m.name.lower() == target_user_name.lower():
                        target = m
                        break
                if not target:
                    for m in message.guild.members:
                        if target_user_name.lower() in m.display_name.lower() or target_user_name.lower() in m.name.lower():
                            target = m
                            break
            if not target: target = message.author
            dm_channel = await target.create_dm()
            await dm_channel.send(msg_content or "📬 Pesan dari bot!")
        elif destination == "channel" and channel_name:
            target_channel = discord.utils.get(message.guild.text_channels, name=channel_name)
            if target_channel:
                await target_channel.send(msg_content or "📬 Pesan dari bot!")
            else:
                await message.channel.send(f"❌ Channel #{channel_name} tidak ditemukan.")
    except discord.Forbidden:
        await message.channel.send(f"❌ Tidak bisa kirim DM. DM mungkin tertutup.")
    except Exception as e:
        log.error(f"📤 Send message error: {e}")


# ============================================================
# SERVER INFO / MODERATE / INVITE / AUDIT LOG HANDLERS
# ============================================================

async def execute_get_server_info_action(message, action):
    info_type = action.get("info_type", "all")
    guild = message.guild
    result = []
    if info_type in ("members", "all"):
        online = [m for m in guild.members if m.status != discord.Status.offline and not m.bot]
        result.append(f"**👥 Online Members ({len(online)}):**")
        for member in online[:20]:
            status_emoji = {"online": "🟢", "idle": "🌙", "dnd": "🔴"}.get(str(member.status), "⚪")
            result.append(f"  {status_emoji} {member.display_name}")
    if info_type in ("voice", "all"):
        result.append(f"\n**🎤 Voice Channels:**")
        for vc in guild.voice_channels:
            members = [m.display_name for m in vc.members if not m.bot]
            result.append(f"  🔊 {vc.name}: {', '.join(members) if members else '(kosong)'}")
    if info_type in ("channels", "all"):
        result.append(f"\n**📝 Text Channels:**")
        for ch in guild.text_channels[:10]:
            result.append(f"  # {ch.name}")
    return "\n".join(result) if result else "Tidak ada info."


async def execute_moderate_action(message, action_data):
    mod_action = action_data.get("action", "kick")
    target_name = action_data.get("target_name", "")
    reason = action_data.get("reason", "No reason provided")
    duration = action_data.get("duration_minutes", 10)
    target_member = None
    for m in message.guild.members:
        if m.display_name.lower() == target_name.lower() or m.name.lower() == target_name.lower():
            target_member = m
            break
    if not target_member:
        await message.channel.send(f"❌ Member **{target_name}** tidak ditemukan.")
        return
    try:
        if mod_action == "kick":
            await target_member.kick(reason=reason)
            await message.channel.send(f"✅ **{target_member.display_name}** di-kick. Reason: {reason}")
        elif mod_action == "ban":
            await target_member.ban(reason=reason)
            await message.channel.send(f"✅ **{target_member.display_name}** di-ban. Reason: {reason}")
        elif mod_action == "timeout":
            await target_member.timeout(timedelta(minutes=duration), reason=reason)
            await message.channel.send(f"✅ **{target_member.display_name}** di-timeout {duration} menit.")
        elif mod_action == "unban":
            bans = [ban async for ban in message.guild.bans()]
            for ban_entry in bans:
                if ban_entry.user.name.lower() == target_name.lower():
                    await message.guild.unban(ban_entry.user, reason=reason)
                    await message.channel.send(f"✅ **{ban_entry.user.name}** di-unban.")
                    return
            await message.channel.send(f"❌ User **{target_name}** tidak ada di ban list.")
    except discord.Forbidden:
        await message.channel.send(f"❌ Bot tidak punya permission untuk {mod_action}.")
    except Exception as e:
        await message.channel.send(f"❌ Error: {e}")


async def execute_invite_action(message, action_data):
    target_name = action_data.get("target_name", "")
    channel_name = action_data.get("channel_name", "")
    uses = action_data.get("max_uses", 1)
    days = action_data.get("days_valid", 1)
    target_channel = message.channel
    if channel_name:
        for ch in message.guild.text_channels:
            if ch.name.lower() == channel_name.lower():
                target_channel = ch
                break
    try:
        invite = await target_channel.create_invite(max_uses=uses, max_age=days * 86400, unique=True)
    except Exception as e:
        await message.channel.send(f"❌ Gagal membuat invite: {e}")
        return
    target_member = None
    for m in message.guild.members:
        if m.display_name.lower() == target_name.lower() or m.name.lower() == target_name.lower():
            target_member = m
            break
    if target_member:
        try:
            await target_member.send(f"📨 **Invite Link** dari {message.guild.name}:\n{invite.url}")
            await message.channel.send(f"✅ Invite sent to **{target_member.display_name}**.")
        except discord.Forbidden:
            await message.channel.send(f"❌ Gagal DM. Link:\n{invite.url}")
    else:
        await message.channel.send(f"⚠️ User **{target_name}** tidak ditemukan. Link:\n{invite.url}")


async def execute_audit_log_action(message, action_data):
    action_type = action_data.get("action_type", "all")
    limit = action_data.get("limit", 10)
    action_map = {
        "kick": discord.AuditLogAction.kick, "ban": discord.AuditLogAction.ban,
        "unban": discord.AuditLogAction.unban, "message_delete": discord.AuditLogAction.message_delete,
        "role_update": discord.AuditLogAction.role_update, "channel_create": discord.AuditLogAction.channel_create,
        "member_update": discord.AuditLogAction.member_update,
    }
    try:
        kwargs = {"limit": limit}
        if action_type != "all" and action_type in action_map:
            kwargs["action"] = action_map[action_type]
        entries = []
        async for entry in message.guild.audit_logs(**kwargs):
            entries.append(entry)
        if not entries:
            await message.channel.send("Tidak ada audit log.")
            return
        lines = [f"**Audit Log** (last {len(entries)} entries):"]
        for e in entries:
            user = e.user.display_name if e.user else "Unknown"
            target = str(e.target) if e.target else "-"
            action_name = str(e.action).replace("AuditLogAction.", "")
            time_str = e.created_at.strftime("%d/%m %H:%M")
            reason = f" | {e.reason}" if e.reason else ""
            lines.append(f"`{time_str}` **{user}** > {action_name} > **{target}**{reason}")
        result = "\n".join(lines)
        if len(result) > 1900: result = result[:1900] + "\n..."
        await message.channel.send(result)
    except discord.Forbidden:
        await message.channel.send("Bot tidak punya permission View Audit Log.")
    except Exception as e:
        await message.channel.send(f"Error: {e}")


# ============================================================
# WAVELINK EVENTS
# ============================================================

@bot.event
async def setup_hook():
    from config import LAVALINK_NODES
    try:
        for node_config in LAVALINK_NODES:
            node = wavelink.Node(
                identifier=node_config["identifier"],
                uri=f"{'https' if node_config['secure'] else 'http'}://{node_config['host']}:{node_config['port']}",
                password=node_config["password"],
            )
            await wavelink.Pool.connect(client=bot, nodes=[node])
        log.info(f"🎵 Wavelink initialized with {len(LAVALINK_NODES)} node(s)")
    except Exception as e:
        log.error(f"❌ Failed to connect Wavelink: {e}")


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    log.info(f"🎵 Lavalink Node '{payload.node.identifier}' ready!")


@bot.event
async def on_wavelink_track_start(payload: wavelink.TrackStartEventPayload):
    from music.player import get_player
    music_player = get_player(payload.player.guild.id)
    if music_player and music_player.now_playing_message:
        try:
            from music.views import create_now_playing_embed, MusicControlView
            embed = create_now_playing_embed(payload.track, payload.player)
            view = MusicControlView(payload.player)
            await music_player.now_playing_message.edit(embed=embed, view=view)
        except: pass


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    from music.player import get_player
    music_player = get_player(payload.player.guild.id)
    if music_player and music_player.auto_play:
        await music_player.play_next()


# ============================================================
# ON READY
# ============================================================

@bot.event
async def on_ready():
    log.info(f"Bot ready: {bot.user.name} ({bot.user.id})")
    log.info(f"Servers: {len(bot.guilds)}")
    log.info(f"Providers: {list_available_providers()}")

    saved_guilds = SettingsManager.get_all_guilds()
    if USE_TURSO:
        log.info(f"DATABASE: CONNECTED | Turso Cloud | {len(saved_guilds)} saved guilds | ✅ Persistent")
    elif os.path.exists(DB_PATH):
        db_size = os.path.getsize(DB_PATH)
        log.info(f"DATABASE: CONNECTED | {DB_PATH} | {db_size} bytes | {len(saved_guilds)} saved guilds | ⚠️ Ephemeral")
    else:
        log.warning(f"DATABASE: NOT FOUND | {DB_PATH}")

    for guild in bot.guilds:
        settings = get_settings(guild.id)
        mode = settings["active_mode"]
        auto = settings["auto_chat"]
        channels = len(settings["enabled_channels"])
        log.info(f"  Guild '{guild.name}' | mode: {mode} | auto_chat: {auto} | channels: {channels}")

    log.info("=" * 50)
    log.info("BOT FULLY READY - ALL SYSTEMS GO")

    try:
        from music.commands import setup as setup_music
        await setup_music(bot)
        log.info("🎵 Music module loaded!")
    except Exception as e:
        log.error(f"❌ Failed to load music: {e}")
        import traceback
        traceback.print_exc()

    try:
        from core.database import init_reminders_table
        from core.scheduler import init_scheduler

        init_reminders_table()
        init_user_locations_table()
        scheduler = init_scheduler(bot)
        await scheduler.start()
        log.info("⏰ Reminder scheduler started!")
    except Exception as e:
        log.error(f"❌ Failed to start scheduler: {e}")
        import traceback
        traceback.print_exc()

    log.info("=" * 50)

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.listening, name=f"{DISCORD_PREFIX}help")
    )


# ============================================================
# ON MESSAGE
# ============================================================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.content.startswith(DISCORD_PREFIX):
        return
    if not message.guild:
        return

    settings = get_settings(message.guild.id)
    should_respond = False

    if settings["auto_chat"] and message.channel.id in settings["enabled_channels"]:
        should_respond = True
    if bot.user in message.mentions:
        should_respond = True
    if not should_respond:
        return

    content = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if not content:
        content = "Hello!"

    # Voice context
    if message.author.voice and message.author.voice.channel:
        settings["user_in_voice"] = True
        settings["user_voice_channel"] = message.author.voice.channel.name
    else:
        settings["user_in_voice"] = False
        settings["user_voice_channel"] = None

    # Attachments
    if message.attachments:
        settings["attachments"] = [
            {"url": att.url, "filename": att.filename, "size": att.size}
            for att in message.attachments if att.size < 10_000_000
        ]
    else:
        settings["attachments"] = []

    # Server info
    try:
        guild = message.guild
        online_members = []
        for m in guild.members:
            if not m.bot and str(m.status) != "offline":
                status_icon = {"online": "🟢", "idle": "🌙", "dnd": "🔴"}.get(str(m.status), "⚪")
                online_members.append(f"{status_icon} {m.display_name}")
        voice_info = []
        for vc in guild.voice_channels:
            vc_members = [m.display_name for m in vc.members if not m.bot]
            voice_info.append(f"#{vc.name}: {', '.join(vc_members) if vc_members else '(kosong)'}")
        text_channels = [f"#{ch.name}" for ch in guild.text_channels]
        all_members = []
        for m in guild.members:
            if not m.bot:
                status_icon = {"online": "🟢", "idle": "🌙", "dnd": "🔴", "offline": "⚫"}.get(str(m.status), "⚪")
                roles = [r.name for r in m.roles if r.name != "@everyone"]
                all_members.append(f"{status_icon} {m.display_name} ({', '.join(roles) if roles else 'no role'})")
        settings["server_info"] = {
            "server_name": guild.name, "total_members": guild.member_count,
            "online_members": online_members, "all_members": all_members,
            "voice_channels": voice_info, "text_channels": text_channels,
        }
    except Exception as e:
        log.warning(f"Failed to get server info: {e}")
        settings["server_info"] = {}

    # User context
    settings["_channel_id"] = message.channel.id
    settings["_user_id"] = message.author.id
    settings["_user_name"] = message.author.display_name

    # User location context
    user_loc = get_user_location(message.author.id)
    if user_loc["found"]:
        settings["_user_location"] = user_loc["location"]
        settings["_user_lat"] = user_loc.get("latitude")
        settings["_user_lon"] = user_loc.get("longitude")
    else:
        settings["_user_location"] = None
        settings["_user_lat"] = None
        settings["_user_lon"] = None

    # Call AI handler
    async with message.channel.typing():
        from core.handler import handle_message
        settings["guild_id"] = message.guild.id
        result = await handle_message(
            content, settings,
            channel_id=message.channel.id,
            user_id=message.author.id,
            user_name=message.author.display_name
        )

        response_text = result["text"]
    fallback_note = result.get("fallback_note")
    if fallback_note:
        response_text += f"\n\n-# {fallback_note}"

    # ── Send text response ──
    if len(response_text) > 2000:
        chunks = _split_message(response_text)
        for chunk in chunks:
            await message.reply(chunk, mention_author=False)
    else:
        await message.reply(response_text, mention_author=False)

    # ── Auto TTS ──
    voice_cfg = settings.get("voice", {})
    if (
        voice_cfg.get("enabled")
        and message.author.voice
        and message.author.voice.channel
        and response_text.strip()
    ):
        await _auto_tts(message, response_text, voice_cfg)

    # ── Delete mention message ──
    try:
        if bot.user in message.mentions:
            await message.delete()
    except (discord.Forbidden, discord.NotFound):
        pass

    # ── Execute actions ──
    for action in result.get("actions", []):
        try:
            action_type = action.get("type", "")
            if action_type == "music": await execute_music_action(message, action)
            elif action_type == "download": await execute_download_action(message, action)
            elif action_type == "image": await execute_image_action(message, action)
            elif action_type == "upload_file": await execute_file_upload_action(message, action)
            elif action_type == "reminder": await execute_reminder_action(message, action)
            elif action_type == "send_message": await execute_send_message_action(message, action)
            elif action_type == "moderate": await execute_moderate_action(message, action)
            elif action_type == "invite": await execute_invite_action(message, action)
            elif action_type == "audit_log": await execute_audit_log_action(message, action)
            elif action_type == "get_server_info":
                info_text = await execute_get_server_info_action(message, action)
                await message.channel.send(info_text)
        except Exception as e:
            log.error(f"🔧 Action error [{action.get('type')}]: {e}")

# ============================================================
# AUTO TTS — Speak AI response in voice channel
# ============================================================

async def _auto_tts(message: discord.Message, text: str, voice_cfg: dict):
    """Auto-generate TTS and play in voice channel"""
    try:
        tts_text = text[:3000] if len(text) > 3000 else text

        result = await generate_tts(
            text=tts_text,
            voice=voice_cfg.get("voice_name") if voice_cfg.get("voice_name") != "auto" else None,
            gender=voice_cfg.get("gender", "female"),
            rate=voice_cfg.get("speed", "+0%"),
            pitch=voice_cfg.get("pitch", "+0Hz"),
        )

        if not result["success"]:
            log.warning(f"🔊 Auto-TTS failed: {result.get('error')}")
            return

        filepath = result["filepath"]
        filename = result["filename"]

        player: wavelink.Player = message.guild.voice_client
        if not player:
            try:
                player = await message.author.voice.channel.connect(cls=wavelink.Player)
                from music.player import MusicPlayer, set_player
                set_player(message.guild.id, MusicPlayer(player))
            except Exception as e:
                log.warning(f"🔊 Cannot join voice: {e}")
                try:
                    discord_file = discord.File(filepath, filename="response.mp3")
                    await message.channel.send(file=discord_file)
                except:
                    pass
                _safe_delete(filepath)
                return

        render_url = os.getenv("RENDER_EXTERNAL_URL", "")
        if not render_url:
            log.warning("🔊 RENDER_EXTERNAL_URL not set")
            _safe_delete(filepath)
            return

        tts_url = f"{render_url}/tts/{filename}"

        try:
            tracks = await wavelink.Playable.search(tts_url)
            if tracks:
                track = tracks[0] if not isinstance(tracks, wavelink.Playlist) else tracks.tracks[0]
                await player.play(track)
                log.info(f"🔊 Auto-TTS playing: {result['voice']} | {result['text_length']} chars")

                async def _cleanup():
                    await asyncio.sleep(60)
                    _safe_delete(filepath)
                    cleanup_old_tts(120)
                asyncio.create_task(_cleanup())
            else:
                discord_file = discord.File(filepath, filename="response.mp3")
                await message.channel.send(file=discord_file)
                _safe_delete(filepath)
        except Exception as e:
            log.warning(f"🔊 Lavalink error: {e}")
            try:
                discord_file = discord.File(filepath, filename="response.mp3")
                await message.channel.send(file=discord_file)
            except:
                pass
            _safe_delete(filepath)
    except Exception as e:
        log.error(f"🔊 Auto-TTS error: {e}")


def _safe_delete(filepath: str):
    try:
        if filepath and os.path.exists(filepath):
            os.unlink(filepath)
    except:
        pass

# ============================================================
# HELPERS
# ============================================================

def _split_message(text: str, limit: int = 2000) -> list:
    if len(text) <= limit: return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        sp = text.rfind('\n', 0, limit)
        if sp == -1 or sp < limit // 2: sp = limit
        chunks.append(text[:sp])
        text = text[sp:].lstrip()
    return chunks


# ============================================================
# ERROR HANDLER
# ============================================================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("🔒 Butuh permission: **Manage Server**")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`")
    elif isinstance(error, commands.CommandInvokeError):
        log.error(f"Command error in {ctx.command}: {error.original}")
        await ctx.send(f"❌ Error: {error.original}")
    else:
        log.error(f"Unhandled error: {error}")


# ============================================================
# HELP COMMAND
# ============================================================

@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    p = DISCORD_PREFIX
    embed = discord.Embed(
        title="🤖 AI Bot Commands",
        color=discord.Color.blue(),
        description=(
            f"**AI Settings:**\n"
            f"🔒 `{p}set` — Konfigurasi mode, provider, model\n"
            f"🔒 `{p}toggle` — Toggle auto-chat ON/OFF\n"
            f"🔒 `{p}channel` — Enable/disable auto-chat channel\n"
            f"`{p}status` — Lihat konfigurasi saat ini\n"
            f"🔒 `{p}monitor` — Health dashboard provider\n"
            f"🔒 `{p}log [n]` — Lihat request log\n"
            f"🔒 `{p}reset` — Reset ke default\n\n"
            f"**Location:**\n"
            f"`{p}setlocation <kota>` — Set lokasi default\n"
            f"`{p}mylocation` — Lihat lokasi tersimpan\n"
            f"`{p}dellocation` — Hapus lokasi\n"
            f"`{p}map <tujuan>` — Rute dari lokasimu\n\n"
            f"**Skills:**\n"
            f"`{p}time [timezone]` — Cek waktu sekarang\n"
            f"`{p}alarm <menit> <pesan>` — Set alarm\n"
            f"`{p}alarms` — Lihat alarm aktif\n"
            f"`{p}calendar [bulan] [tahun]` — Tampilkan kalender\n"
            f"`{p}countdown <YYYY-MM-DD>` — Hitung mundur\n"
            f"`{p}weather [kota]` — Cek cuaca\n\n"
            f"**Voice (Auto-TTS):**\n"
            f"`{p}voice` — Status & settings\n"
            f"`{p}voice on` / `off` — Toggle suara\n"
            f"`{p}voice speed cepat` — Kecepatan bicara\n"
            f"`{p}voice gender male` — Ganti gender\n"
            f"`{p}voice set gadis` — Pilih voice\n"
            f"`{p}voice test` — Test suara\n"
            f"`{p}voice list` — Daftar voice\n\n"
            f"**Music:**\n"
            f"`{p}play <lagu>` — Play music\n"
            f"`{p}skip` / `{p}stop` / `{p}pause` / `{p}resume`\n"
            f"`{p}queue` / `{p}np` / `{p}volume <0-100>`\n"
            f"`{p}loop` / `{p}shuffle` / `{p}lyrics [judul]`\n\n"
            f"**💡 Mention {ctx.bot.user.mention}:**\n"
            f"• Chat / tanya apapun\n"
            f"• *\"cuaca gimana?\"* (pakai lokasi default)\n"
            f"• *\"puterin lagu ...\"* / *\"skip\"*\n\n"
            f"**Memory:**\n"
            f"`{p}memory` — Status memory\n"
            f"`{p}clear` — Hapus memory channel\n"
            f"`{p}clear all` — Hapus semua memory server"
        )
    )
    await ctx.send(embed=embed)


# ============================================================
# SET COMMAND
# ============================================================

@bot.command(name="set")
@commands.has_permissions(manage_guild=True)
async def set_cmd(ctx: commands.Context):
    settings = get_settings(ctx.guild.id)
    from ui.embeds import create_settings_panel, SettingsView
    embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)

    async def on_update(interaction: discord.Interaction, key: str, value):
        nonlocal settings
        if key == "save_profile":
            mode = value["mode"]
            settings["profiles"][mode]["provider"] = value["provider"]
            settings["profiles"][mode]["model"] = value["model"]
            if mode == "search" and "engine" in value:
                settings["profiles"][mode]["engine"] = value["engine"]
            save_settings(ctx.guild.id)
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            embed.set_footer(text=f"✅ Saved!")
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)
        elif key == "auto_chat":
            settings["auto_chat"] = value
            save_settings(ctx.guild.id)
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)
        elif key == "auto_detect":
            settings["auto_detect"] = value
            save_settings(ctx.guild.id)
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)
        elif key == "active_mode":
            settings["active_mode"] = value
            save_settings(ctx.guild.id)
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)
        elif key == "test_result":
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            embed.set_footer(text=value["msg"])
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)
        elif key == "reset":
            SettingsManager.reset(ctx.guild.id)
            settings = get_settings(ctx.guild.id)
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            embed.set_footer(text="🔄 Reset!")
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)
        elif key == "back":
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)

    view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
    await ctx.send(embed=embed, view=view)


# ============================================================
# SIMPLE COMMANDS
# ============================================================

@bot.command(name="toggle")
@commands.has_permissions(manage_guild=True)
async def toggle_cmd(ctx):
    settings = get_settings(ctx.guild.id)
    settings["auto_chat"] = not settings["auto_chat"]
    save_settings(ctx.guild.id)
    state = "🟢 ON" if settings["auto_chat"] else "🔴 OFF"
    await ctx.send(f"Auto-chat: {state} (saved! ✅)")


@bot.command(name="channel")
@commands.has_permissions(manage_guild=True)
async def channel_cmd(ctx):
    settings = get_settings(ctx.guild.id)
    ch = ctx.channel.id
    if ch in settings["enabled_channels"]:
        settings["enabled_channels"].remove(ch)
        save_settings(ctx.guild.id)
        await ctx.send(f"🔴 {ctx.channel.mention} dihapus dari auto-chat (saved! ✅)")
    else:
        settings["enabled_channels"].append(ch)
        save_settings(ctx.guild.id)
        await ctx.send(f"🟢 {ctx.channel.mention} ditambahkan ke auto-chat (saved! ✅)")


@bot.command(name="status")
async def status_cmd(ctx):
    settings = get_settings(ctx.guild.id)
    profiles = settings["profiles"]
    lines = ["**⚙️ Current Configuration** 💾\n"]
    for mode in ["normal", "reasoning", "search"]:
        p = profiles[mode]
        icon_m = MODE_ICONS.get(mode, "📦")
        icon_p = PROVIDER_ICONS.get(p["provider"], "📦")
        active = " 📌" if mode == settings["active_mode"] else ""
        line = f"{icon_m} **{mode.title()}**{active}: {icon_p} `{p['provider']}` → `{p['model']}`"
        if mode == "search":
            icon_s = SEARCH_ICONS.get(p.get("engine", "duckduckgo"), "🔍")
            line += f" + {icon_s} `{p.get('engine', 'duckduckgo')}`"
        lines.append(line)
    auto_chat = "🟢 ON" if settings["auto_chat"] else "🔴 OFF"
    auto_detect = "🟢 ON" if settings["auto_detect"] else "🔴 OFF"
    storage = "☁️ Turso Cloud" if USE_TURSO else "📁 SQLite Local"
    lines.append(f"\nAuto-chat: {auto_chat} | Auto-detect: {auto_detect}")
    lines.append(f"Channels: {len(settings['enabled_channels'])} enabled")
    lines.append(f"\n-# 💾 Storage: {storage}")
    embed = discord.Embed(description="\n".join(lines), color=discord.Color.blue())
    await ctx.send(embed=embed)


@bot.command(name="monitor")
@commands.has_permissions(manage_guild=True)
async def monitor_cmd(ctx):
    available = list_available_providers()
    lines = ["**📊 Provider Health**\n"]
    for name, provider in PROVIDERS.items():
        icon = PROVIDER_ICONS.get(name, "📦")
        status = "🟢" if name in available else "⚪"
        lines.append(f"{status} {icon} **{provider.name}** • `{provider.rate_limit}`")
    lines.append(f"\n🟢 Available  ⚪ No API Key")
    embed = discord.Embed(description="\n".join(lines), color=discord.Color.blue())
    await ctx.send(embed=embed)


@bot.command(name="log")
@commands.has_permissions(manage_guild=True)
async def log_cmd(ctx, n: int = 10):
    from core.handler import request_logs
    guild_logs = [l for l in request_logs if l.get("guild_id") == ctx.guild.id]
    recent = guild_logs[-n:] if guild_logs else []
    if not recent:
        await ctx.send("📋 Belum ada log.")
        return
    lines = ["**📋 Recent Logs**\n"]
    for entry in reversed(recent):
        icon = PROVIDER_ICONS.get(entry["provider"], "📦")
        status = "✅" if entry["success"] else "❌"
        fb = " ↩️" if entry.get("is_fallback") else ""
        lines.append(f"`{entry['time']}` {status}{fb} {icon} `{entry['provider']}/{entry['model']}` ({entry['latency']:.1f}s)")
    embed = discord.Embed(description="\n".join(lines[:20]), color=discord.Color.blue())
    await ctx.send(embed=embed)


@bot.command(name="reset")
@commands.has_permissions(manage_guild=True)
async def reset_cmd(ctx):
    SettingsManager.reset(ctx.guild.id)
    await ctx.send("🔄 Reset ke default berhasil. (saved! ✅)")


# ============================================================
# MEMORY COMMANDS
# ============================================================

@bot.command(name="clear", aliases=["forget", "lupa"])
async def clear_cmd(ctx, scope: str = "channel"):
    from core.database import clear_conversation
    if scope == "all":
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send("❌ Hanya admin yang bisa hapus semua memory server!")
            return
        clear_conversation(ctx.guild.id)
        await ctx.send("🧹 Semua memory di server ini dihapus!")
    else:
        clear_conversation(ctx.guild.id, ctx.channel.id)
        await ctx.send(f"🧹 Memory di {ctx.channel.mention} dihapus!")


@bot.command(name="memory", aliases=["mem"])
async def memory_cmd(ctx):
    from core.database import get_memory_stats, get_conversation, MAX_MEMORY_MESSAGES
    stats = get_memory_stats(ctx.guild.id)
    channel_msgs = len(get_conversation(ctx.guild.id, ctx.channel.id))
    storage = "☁️ Turso Cloud" if USE_TURSO else "📁 SQLite Local"
    embed = discord.Embed(title="🧠 Conversation Memory", color=discord.Color.purple())
    embed.add_field(name="Channel Ini", value=f"`{channel_msgs}` / `{MAX_MEMORY_MESSAGES}` pesan", inline=True)
    embed.add_field(name="Server Total", value=f"`{stats['channels']}` ch\n`{stats['total_messages']}` pesan", inline=True)
    embed.add_field(name="Storage", value=f"💾 {storage}", inline=True)
    await ctx.send(embed=embed)


# ============================================================
# SKILL COMMANDS
# ============================================================

from skills import (
    get_current_time, get_time_difference,
    set_alarm, list_alarms, cancel_alarm,
    get_calendar, days_until, get_weather
)


@bot.command(name="time", aliases=["waktu"])
async def time_cmd(ctx, timezone: str = "Asia/Jakarta"):
    result = get_current_time(timezone)
    if result["success"]:
        embed = discord.Embed(title="🕐 Waktu Sekarang", description=f"**{result['full']}**", color=discord.Color.blue())
        embed.add_field(name="Jam", value=result['time'], inline=True)
        embed.add_field(name="Tanggal", value=result['date'], inline=True)
        embed.add_field(name="Hari", value=result['day'], inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Error: {result['error']}")


@bot.command(name="alarm")
async def alarm_cmd(ctx, minutes: int, *, message: str = "⏰ Alarm!"):
    if minutes < 1 or minutes > 1440:
        await ctx.send("❌ Alarm: 1-1440 menit")
        return
    async def alarm_callback(alarm_data):
        user = ctx.guild.get_member(alarm_data["user_id"])
        if user:
            try: await ctx.channel.send(f"⏰ {user.mention} **ALARM:** {alarm_data['message']}")
            except: pass
    result = await set_alarm(ctx.guild.id, ctx.author.id, minutes, message, alarm_callback)
    if result["success"]:
        await ctx.send(f"⏰ Alarm: **{minutes} menit** lagi ({result['trigger_time']})\n📝 {message}")


@bot.command(name="alarms", aliases=["myalarms"])
async def alarms_cmd(ctx):
    active = list_alarms(ctx.guild.id, ctx.author.id)
    if not active:
        await ctx.send("📭 Tidak ada alarm aktif.")
        return
    lines = ["**⏰ Alarm Aktif:**\n"]
    for i, alarm in enumerate(active, 1):
        trigger = alarm['trigger_time'].strftime("%H:%M:%S")
        remaining = (alarm['trigger_time'] - datetime.now()).total_seconds() / 60
        lines.append(f"{i}. `{trigger}` (~{int(remaining)} menit) - {alarm['message']}")
    await ctx.send("\n".join(lines))


@bot.command(name="calendar", aliases=["kalender", "cal"])
async def calendar_cmd(ctx, month_input: str = None, year: int = None):
    month = parse_month(month_input) if month_input else None
    if month_input and month is None:
        await ctx.send(f"❌ Bulan `{month_input}` tidak dikenali!")
        return
    result = get_calendar(year, month)
    if result["success"]:
        embed = discord.Embed(title=f"📅 {result['month_name']} {result['year']}",
            description=result["calendar_text"], color=discord.Color.green())
        embed.set_footer(text=f"{result['days_in_month']} hari")
        await ctx.send(embed=embed)


@bot.command(name="countdown", aliases=["hitung"])
async def countdown_cmd(ctx, target_date: str):
    result = days_until(target_date)
    if result["success"]:
        if result["is_today"]: msg = f"🎉 **Hari ini adalah {target_date}!**"
        elif result["is_past"]: msg = f"📅 {target_date} sudah lewat **{abs(result['days_remaining'])} hari**"
        else: msg = f"⏳ **{result['days_remaining']} hari** lagi menuju {target_date}"
        await ctx.send(msg)
    else:
        await ctx.send(f"❌ {result['error']}")


@bot.command(name="weather", aliases=["cuaca"])
async def weather_cmd(ctx, *, city: str = None):
    if not city:
        loc = get_user_location(ctx.author.id)
        if loc["found"]:
            city = loc["location"]
        else:
            await ctx.send(
                f"🌤️ Kota mana?\n"
                f"• `{DISCORD_PREFIX}weather Jakarta`\n"
                f"• Atau set default: `{DISCORD_PREFIX}setlocation Jakarta`"
            )
            return

    async with ctx.typing():
        result = await get_weather(city)

    if result["success"]:
        embed = discord.Embed(title=f"🌤️ Cuaca di {result['city']}",
            description=f"**{result['description']}**", color=discord.Color.orange())
        embed.add_field(name="🌡️ Suhu", value=f"{result['temp']}°C", inline=True)
        embed.add_field(name="💨 Terasa", value=f"{result['feels_like']}°C", inline=True)
        embed.add_field(name="💧 Kelembapan", value=f"{result['humidity']}%", inline=True)
        embed.add_field(name="🌬️ Angin", value=f"{result['wind_speed']} km/h", inline=True)

        source_loc = get_user_location(ctx.author.id)
        if source_loc["found"] and city == source_loc["location"]:
            embed.set_footer(text="📍 Menggunakan lokasi default kamu")

        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {result['error']}")


# ============================================================
# LOCATION COMMANDS
# ============================================================

@bot.command(name="setlocation", aliases=["setloc", "lokasi"])
async def setlocation_cmd(ctx, *, location: str):
    lat, lon = await geocode_location(location)
    success = set_user_location(ctx.author.id, location, lat, lon)

    if success:
        coord_text = ""
        if lat is not None and lon is not None:
            coord_text = f"\n📍 Koordinat: `{lat:.4f}, {lon:.4f}`"
        await ctx.send(
            f"✅ Lokasi tersimpan: **{location}**{coord_text}\n"
            f"💾 Persistent (tidak hilang saat restart)\n\n"
            f"Sekarang bisa pakai:\n"
            f"• `{DISCORD_PREFIX}weather` tanpa ketik kota\n"
            f"• `{DISCORD_PREFIX}map <tujuan>` untuk rute\n"
            f"• Mention bot: *cuaca gimana?*"
        )
    else:
        await ctx.send("❌ Gagal menyimpan lokasi.")


@bot.command(name="mylocation", aliases=["myloc", "lokasiku"])
async def mylocation_cmd(ctx):
    loc = get_user_location(ctx.author.id)
    if not loc["found"]:
        await ctx.send(f"📍 Belum set lokasi. Gunakan `{DISCORD_PREFIX}setlocation Jakarta`")
        return

    embed = discord.Embed(title="📍 Lokasi Tersimpan", color=discord.Color.green())
    embed.add_field(name="Lokasi", value=loc["location"], inline=True)
    if loc.get("latitude") is not None and loc.get("longitude") is not None:
        embed.add_field(name="Koordinat", value=f"`{loc['latitude']:.4f}, {loc['longitude']:.4f}`", inline=True)
        maps_url = f"https://www.google.com/maps?q={loc['latitude']},{loc['longitude']}"
        embed.add_field(name="Maps", value=f"[Buka di Google Maps]({maps_url})", inline=False)
    embed.set_footer(text=f"Gunakan {DISCORD_PREFIX}setlocation <kota> untuk ubah")
    await ctx.send(embed=embed)


@bot.command(name="dellocation", aliases=["delloc", "hapuslokasi"])
async def dellocation_cmd(ctx):
    if delete_user_location(ctx.author.id):
        await ctx.send("✅ Lokasi kamu sudah dihapus.")
    else:
        await ctx.send("📍 Kamu tidak punya lokasi tersimpan.")


@bot.command(name="map", aliases=["route", "rute", "direction", "arah"])
async def map_cmd(ctx, *, destination: str):
    loc = get_user_location(ctx.author.id)
    if not loc["found"]:
        await ctx.send(f"📍 Belum set lokasi! `{DISCORD_PREFIX}setlocation <kota>` dulu.")
        return

    origin = loc["location"]
    if loc.get("latitude") is not None and loc.get("longitude") is not None:
        maps_url = f"https://www.google.com/maps/dir/{loc['latitude']},{loc['longitude']}/{destination.replace(' ', '+')}"
    else:
        maps_url = f"https://www.google.com/maps/dir/{origin.replace(' ', '+')}/" + destination.replace(' ', '+')

    embed = discord.Embed(title="🗺️ Rute Perjalanan", color=discord.Color.blue())
    embed.add_field(name="📍 Dari", value=origin, inline=True)
    embed.add_field(name="🏁 Ke", value=destination, inline=True)
    embed.add_field(name="🔗 Google Maps", value=f"[Buka Directions]({maps_url})", inline=False)
    embed.set_footer(text="Klik link untuk buka navigasi")
    await ctx.send(embed=embed)


# ============================================================
# REMINDER COMMANDS
# ============================================================

@bot.command(name="reminders", aliases=["myreminders", "reminderlist"])
async def reminders_cmd(ctx):
    from core.database import get_user_reminders
    reminders = get_user_reminders(ctx.guild.id, ctx.author.id)
    if not reminders:
        await ctx.send("📭 Tidak ada reminder aktif.")
        return
    embed = discord.Embed(title="⏰ Reminder Aktif", color=discord.Color.orange())
    for r in reminders[:10]:
        next_trigger = r.get("next_trigger", "?")
        if next_trigger and "T" in str(next_trigger):
            next_trigger = next_trigger.split("T")[1][:5]
        trigger_type = r.get("trigger_type", "once")
        type_emoji = {"daily": "🔄", "weekly": "📅", "once": "1️⃣", "minutes": "⏱️"}.get(trigger_type, "⏰")
        embed.add_field(name=f"{type_emoji} #{r['id']} — {next_trigger}",
            value=f"{r['message'][:50]}", inline=False)
    embed.set_footer(text=f"Total: {len(reminders)} | {DISCORD_PREFIX}cancelreminder <id>")
    await ctx.send(embed=embed)


@bot.command(name="cancelreminder", aliases=["delreminder", "rmreminder"])
async def cancel_reminder_cmd(ctx, reminder_id: int):
    from core.database import delete_reminder
    if delete_reminder(reminder_id, ctx.author.id):
        await ctx.send(f"✅ Reminder #{reminder_id} dihapus!")
    else:
        await ctx.send(f"❌ Reminder #{reminder_id} tidak ditemukan.")

# ============================================================
# VOICE SETTINGS COMMANDS
# ============================================================

@bot.command(name="voice", aliases=["tts", "suara"])
async def voice_cmd(ctx: commands.Context, action: str = None, *, value: str = None):
    """Voice settings for auto-TTS"""
    settings = get_settings(ctx.guild.id)
    voice_cfg = settings.setdefault("voice", {
        "enabled": False, "speed": "+0%",
        "gender": "female", "voice_name": "auto", "pitch": "+0Hz",
    })

    if not action:
        status = "🟢 ON" if voice_cfg.get("enabled") else "🔴 OFF"
        speed = voice_cfg.get("speed", "+0%")
        gender_icon = "♀️" if voice_cfg.get("gender") == "female" else "♂️"
        voice_name = voice_cfg.get("voice_name", "auto")

        speed_label = speed
        for label, val in SPEED_PRESETS.items():
            if val == speed:
                speed_label = f"{label} ({speed})"
                break

        embed = discord.Embed(title="🔊 Voice Settings", color=discord.Color.blue())
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Kecepatan", value=speed_label, inline=True)
        embed.add_field(name="Gender", value=f"{gender_icon} {voice_cfg.get('gender', 'female')}", inline=True)
        embed.add_field(name="Voice", value=f"`{voice_name}`", inline=True)
        embed.add_field(
            name="Cara Pakai",
            value=(
                f"`{DISCORD_PREFIX}voice on` / `off` — Toggle\n"
                f"`{DISCORD_PREFIX}voice speed cepat` — Kecepatan\n"
                f"`{DISCORD_PREFIX}voice gender male` — Gender\n"
                f"`{DISCORD_PREFIX}voice set gadis` — Pilih voice\n"
                f"`{DISCORD_PREFIX}voice list` — Daftar voice\n"
                f"`{DISCORD_PREFIX}voice test` — Test suara"
            ),
            inline=False
        )
        if voice_cfg.get("enabled"):
            embed.set_footer(text="Bot otomatis bicara saat kamu di voice channel")
        else:
            embed.set_footer(text="Voice OFF — bot hanya kirim teks")
        await ctx.send(embed=embed)
        return

    action = action.lower()

    if action == "on":
        voice_cfg["enabled"] = True
        save_settings(ctx.guild.id)
        await ctx.send("🔊 Voice **ON**! Bot akan bicara di voice channel.\nPastikan kamu sudah join VC.")

    elif action == "off":
        voice_cfg["enabled"] = False
        save_settings(ctx.guild.id)
        await ctx.send("🔇 Voice **OFF**. Bot hanya kirim teks.")

    elif action in ("speed", "kecepatan", "spd"):
        if not value:
            await ctx.send(
                f"🔊 Speed: `{voice_cfg.get('speed', '+0%')}`\n"
                f"Pilihan: `lambat` `normal` `cepat` `fastest` `turbo`\n"
                f"Atau custom: `+30%` atau `1.5`"
            )
            return
        parsed = parse_speed(value)
        voice_cfg["speed"] = parsed
        save_settings(ctx.guild.id)
        await ctx.send(f"🔊 Speed → **{value}** (`{parsed}`) saved! ✅")

    elif action in ("gender", "suara"):
        if not value:
            await ctx.send(f"🔊 Gender: `{voice_cfg.get('gender')}`\nPilihan: `female` / `male`")
            return
        gender = "male" if value.lower() in ("male", "m", "laki", "cowok", "pria") else "female"
        voice_cfg["gender"] = gender
        save_settings(ctx.guild.id)
        icon = "♂️" if gender == "male" else "♀️"
        await ctx.send(f"🔊 Gender → {icon} **{gender}** saved! ✅")

    elif action in ("set", "pilih"):
        if not value:
            await ctx.send(
                f"🔊 Voice: `{voice_cfg.get('voice_name', 'auto')}`\n"
                f"Pilihan: `auto` `gadis` `ardi` `jenny` `guy` `nanami` `sonia`\n"
                f"Lihat semua: `{DISCORD_PREFIX}voice list`"
            )
            return
        voice_cfg["voice_name"] = value.lower()
        save_settings(ctx.guild.id)
        await ctx.send(f"🔊 Voice → **{value}** saved! ✅")

    elif action in ("pitch", "nada"):
        if not value:
            await ctx.send(f"🔊 Pitch: `{voice_cfg.get('pitch', '+0Hz')}`\nContoh: `+5Hz` `-10Hz`")
            return
        if not value.endswith("Hz"):
            value = f"{value}Hz"
        if not value.startswith(('+', '-')):
            value = f"+{value}"
        voice_cfg["pitch"] = value
        save_settings(ctx.guild.id)
        await ctx.send(f"🔊 Pitch → **{value}** saved! ✅")

    elif action in ("list", "daftar", "voices"):
        embed = discord.Embed(title="🔊 Daftar Voice", color=discord.Color.blue())
        lang_names = {
            "id": "🇮🇩 Indonesia", "en": "🇺🇸 English", "ja": "🇯🇵 Japanese",
            "ko": "🇰🇷 Korean", "zh": "🇨🇳 Chinese", "es": "🇪🇸 Spanish",
            "fr": "🇫🇷 French", "de": "🇩🇪 German", "ar": "🇸🇦 Arabic",
        }
        langs = {}
        for key, vid in VOICES.items():
            lc = key.split("-")[0]
            if lc not in langs: langs[lc] = []
            g = "♀️" if "female" in key else "♂️"
            langs[lc].append(f"{g} `{vid}`")
        for lc, vl in langs.items():
            embed.add_field(name=lang_names.get(lc, lc), value="\n".join(vl), inline=True)
        alias_text = "\n".join(f"`{k}` → {v}" for k, v in list(VOICE_ALIASES.items())[:6])
        embed.add_field(name="⚡ Shortcut", value=alias_text, inline=False)
        embed.set_footer(text=f"{DISCORD_PREFIX}voice set gadis | {DISCORD_PREFIX}voice set auto")
        await ctx.send(embed=embed)

    elif action in ("test", "coba"):
        if not ctx.author.voice:
            await ctx.send("❌ Join voice channel dulu!")
            return
        test_text = value or "Halo! Ini test suara bot. Apakah kamu bisa dengar?"
        result = await generate_tts(
            text=test_text,
            voice=voice_cfg.get("voice_name") if voice_cfg.get("voice_name") != "auto" else None,
            gender=voice_cfg.get("gender", "female"),
            rate=voice_cfg.get("speed", "+0%"),
            pitch=voice_cfg.get("pitch", "+0Hz"),
        )
        if not result["success"]:
            await ctx.send(f"❌ TTS gagal: {result.get('error')}")
            return
        filepath = result["filepath"]
        filename = result["filename"]
        try:
            player: wavelink.Player = ctx.guild.voice_client
            if not player:
                player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
                from music.player import MusicPlayer, set_player
                set_player(ctx.guild.id, MusicPlayer(player))
            render_url = os.getenv("RENDER_EXTERNAL_URL", "")
            if render_url:
                tts_url = f"{render_url}/tts/{filename}"
                tracks = await wavelink.Playable.search(tts_url)
                if tracks:
                    track = tracks[0] if not isinstance(tracks, wavelink.Playlist) else tracks.tracks[0]
                    await player.play(track)
                    await ctx.send(f"🔊 *Test...*\n-# Voice: `{result['voice']}` | Speed: `{voice_cfg.get('speed')}`")
                    async def _cl():
                        await asyncio.sleep(30)
                        _safe_delete(filepath)
                    asyncio.create_task(_cl())
                    return
            discord_file = discord.File(filepath, filename="test.mp3")
            await ctx.send(content=f"🔊 `{result['voice']}`", file=discord_file)
            _safe_delete(filepath)
        except Exception as e:
            discord_file = discord.File(filepath, filename="test.mp3")
            await ctx.send(file=discord_file)
            _safe_delete(filepath)

    else:
        await ctx.send(f"❌ `{action}` tidak dikenal. Ketik `{DISCORD_PREFIX}voice` untuk bantuan.")

# ============================================================
# RUN — MUST BE LAST!
# ============================================================

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        log.error("DISCORD_TOKEN not found in .env")
        exit(1)

    from server import keep_alive, self_ping
    keep_alive()

    log.info("Starting bot...")

    async def run_bot():
        async with bot:
            bot.loop.create_task(self_ping())
            await bot.start(DISCORD_TOKEN)

    asyncio.run(run_bot())
