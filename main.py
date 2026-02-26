"""
Discord AI Bot - Entry Point
Multi-provider AI with fallback system
Settings persist via SQLite!
"""

import discord
from discord.ext import commands
import wavelink
import asyncio
import logging
from datetime import datetime
from config import (
    DISCORD_TOKEN,
    DISCORD_PREFIX,
    DEFAULTS,
    PROVIDERS,
    list_available_providers
)
from core.database import init_db, SettingsManager, DEFAULT_SETTINGS

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
log.info("SQLite database ready!")

# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(DISCORD_PREFIX, ".", ","),
    intents=intents,
    help_command=None
)

# ============================================================
# PROVIDER ICONS
# ============================================================

PROVIDER_ICONS = {
    "groq":        "🐆",
    "openrouter":  "🧭",
    "pollinations":"🐝",
    "gemini":      "🔷",
    "cloudflare":  "☁️",
    "huggingface": "🤗",
    "cerebras":    "🧠",
    "cohere":      "🧵",
    "siliconflow": "🧪",
    "routeway":    "🛣️",
    "mlvoca":      "🦙",
    "puter":       "☁️",
}

SEARCH_ICONS = {
    "duckduckgo": "🦆",
    "tavily":     "🔎",
    "brave":      "🦁",
    "serper":     "📡",
    "jina":       "💎",
}

MODE_ICONS = {
    "normal":    "💬",
    "reasoning": "🧠",
    "search":    "🔍",
}

# ============================================================
# MONTH ALIASES (for calendar command)
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
# MUSIC ACTION HANDLER — Execute AI music commands
# ============================================================

async def execute_music_action(message: discord.Message, action: dict):
    """Execute music action triggered by AI tool calling"""
    from music.player import MusicPlayer, get_player, set_player, remove_player
    from music.views import create_now_playing_embed, MusicControlView
    
    act = action.get("action", "play")
    query = action.get("query", "")
    
    log.info(f"🎵 Executing music action: {act} | query: {query}")
    
    # ── PLAY ──
    if act == "play":
        if not message.author.voice:
            # AI should have already told user, but just in case
            return
        
        player: wavelink.Player = message.guild.voice_client
        
        if not player:
            try:
                player = await message.author.voice.channel.connect(cls=wavelink.Player)
                music_player = MusicPlayer(player)
                set_player(message.guild.id, music_player)
                log.info(f"🎵 Joined voice: {message.author.voice.channel.name}")
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
                
                embed = discord.Embed(
                    title="📋 Playlist Added",
                    description=f"**{tracks.name}**\n{len(tracks.tracks)} tracks added",
                    color=0x1DB954
                )
                if tracks.artwork:
                    embed.set_thumbnail(url=tracks.artwork)
                await message.channel.send(embed=embed)
            else:
                track = tracks[0]
                track.requester = message.author
                
                if player.playing:
                    await music_player.add_track(track)
                    embed = discord.Embed(
                        title="➕ Added to Queue",
                        description=f"**[{track.title}]({track.uri})**\n{track.author}",
                        color=0x1DB954
                    )
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
    
    # ── SKIP ──
    elif act == "skip":
        music_player = get_player(message.guild.id)
        if music_player and music_player.is_playing:
            current = music_player.current
            await music_player.skip()
            log.info(f"🎵 Skipped: {current.title if current else 'unknown'}")
        else:
            log.warning("🎵 Skip requested but nothing playing")
    
    # ── STOP ──
    elif act == "stop":
        player: wavelink.Player = message.guild.voice_client
        if player:
            music_player = get_player(message.guild.id)
            if music_player:
                await music_player.clear_queue()
            await player.disconnect()
            remove_player(message.guild.id)
            log.info("🎵 Stopped and disconnected")
    
    # ── PAUSE ──
    elif act == "pause":
        player: wavelink.Player = message.guild.voice_client
        if player and player.playing:
            await player.pause(True)
            log.info("🎵 Paused")
    
    # ── RESUME ──
    elif act == "resume":
        player: wavelink.Player = message.guild.voice_client
        if player and player.paused:
            await player.pause(False)
            log.info("🎵 Resumed")

# ============================================================
# EVENTS
# ============================================================

# ============================================================
# WAVELINK EVENTS (Music System)
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
    player = payload.player
    track = payload.track
    from music.player import get_player
    music_player = get_player(player.guild.id)
    if music_player and music_player.now_playing_message:
        try:
            from music.views import create_now_playing_embed, MusicControlView
            embed = create_now_playing_embed(track, player)
            view = MusicControlView(player)
            await music_player.now_playing_message.edit(embed=embed, view=view)
        except: pass

@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player = payload.player
    from music.player import get_player
    music_player = get_player(player.guild.id)
    if music_player and music_player.auto_play:
        await music_player.play_next()

@bot.event
async def on_ready():
    log.info(f"Bot ready: {bot.user.name} ({bot.user.id})")
    log.info(f"Servers: {len(bot.guilds)}")
    log.info(f"Providers: {list_available_providers()}")
    
    import os
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "bot.db")
    if os.path.exists(db_path):
        db_size = os.path.getsize(db_path)
        saved_guilds = SettingsManager.get_all_guilds()
        log.info(f"DATABASE: CONNECTED | {db_path} | {db_size} bytes | {len(saved_guilds)} saved guilds")
    else:
        log.warning(f"DATABASE: NOT FOUND | {db_path}")
    
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

    log.info("=" * 50)
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{DISCORD_PREFIX}help"
        )
    )


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

    if settings["auto_chat"]:
        if message.channel.id in settings["enabled_channels"]:
            should_respond = True

    if bot.user in message.mentions:
        should_respond = True

    if not should_respond:
        return

    content = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if not content:
        content = "Hello!"

    # ── Pass voice channel context to handler ──
    if message.author.voice and message.author.voice.channel:
        settings["user_in_voice"] = True
        settings["user_voice_channel"] = message.author.voice.channel.name
    else:
        settings["user_in_voice"] = False
        settings["user_voice_channel"] = None

    async with message.channel.typing():
        from core.handler import handle_message
        settings["guild_id"] = message.guild.id
        result = await handle_message(content, settings, channel_id=message.channel.id, user_id=message.author.id, user_name=message.author.display_name)

    response_text = result["text"]
    fallback_note = result.get("fallback_note")

    if fallback_note:
        response_text += f"\n\n-# {fallback_note}"

    # ── Send AI response ──
    if len(response_text) > 2000:
        chunks = _split_message(response_text)
        for chunk in chunks:
            await message.reply(chunk, mention_author=False)
    else:
        await message.reply(response_text, mention_author=False)

    # ── Execute music actions (if any) ──
    for action in result.get("actions", []):
        if action.get("type") == "music":
            try:
                await execute_music_action(message, action)
            except Exception as e:
                log.error(f"🎵 Music action error: {e}")

# ============================================================
# HELPERS
# ============================================================

def _split_message(text: str, limit: int = 2000) -> list:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        sp = text.rfind('\n', 0, limit)
        if sp == -1 or sp < limit // 2:
            sp = limit
        chunks.append(text[:sp])
        text = text[sp:].lstrip()
    return chunks

# ============================================================
# COMMANDS
# ============================================================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`")
    elif isinstance(error, commands.CommandInvokeError):
        log.error(f"Command error in {ctx.command}: {error.original}")
        await ctx.send(f"❌ Error: {error.original}")
    else:
        log.error(f"Unhandled error: {error}")

@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    p = DISCORD_PREFIX
    embed = discord.Embed(
        title="🤖 AI Bot Commands",
        color=discord.Color.blue(),
        description=(
            f"**AI Settings:**\n"
            f"`{p}set` — Konfigurasi mode, provider, model\n"
            f"`{p}toggle` — Toggle auto-chat ON/OFF\n"
            f"`{p}channel` — Enable/disable auto-chat channel\n"
            f"`{p}status` — Lihat konfigurasi saat ini\n"
            f"`{p}monitor` — Health dashboard provider\n"
            f"`{p}log [n]` — Lihat request log\n"
            f"`{p}reset` — Reset ke default\n\n"
            f"**Skills:**\n"
            f"`{p}time [timezone]` — Cek waktu sekarang\n"
            f"`{p}alarm <menit> <pesan>` — Set alarm\n"
            f"`{p}alarms` — Lihat alarm aktif\n"
            f"`{p}calendar [bulan] [tahun]` — Tampilkan kalender\n"
            f"`{p}countdown <YYYY-MM-DD>` — Hitung mundur\n"
            f"`{p}weather <kota>` — Cek cuaca\n\n"
            f"**Music:**\n"
            f"`{p}play <lagu>` — Play music\n"
            f"`{p}skip` — Skip track\n"
            f"`{p}queue` — Lihat antrian\n"
            f"`{p}np` — Now playing\n"
            f"`{p}pause` / `{p}resume` — Pause/Resume\n"
            f"`{p}stop` — Stop & disconnect\n"
            f"`{p}volume <0-100>` — Set volume\n"
            f"`{p}loop` / `{p}shuffle` — Toggle loop/shuffle\n"
            f"`{p}lyrics [judul]` — Lihat lyrics\n"
            f"`{p}fav` — Favorite commands\n\n"
            f"**💡 Atau mention {ctx.bot.user.mention}:**\n"
            f"• Chat / tanya apapun\n"
            f"• *\"puterin lagu Bohemian Rhapsody\"*\n"
            f"• *\"skip lagunya\"* / *\"stop musik\"*\n"
            f"• *\"translate ke English: aku lagi gabut\"*\n"
            f"• *\"cuaca Jakarta gimana?\"*\n\n"
            f"**Memory:**\n"
            f"`{p}memory` — Lihat status memory\n"
            f"`{p}clear` — Hapus memory channel\n"
            f"`{p}clear all` — Hapus semua memory server"
        )
    )
    await ctx.send(embed=embed)

# ============================================================
# !SET — ALL-IN-ONE SETTINGS
# ============================================================

@bot.command(name="set")
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

            icon_p = PROVIDER_ICONS.get(value["provider"], "📦")
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            embed.set_footer(text=f"✅ {MODE_ICONS[mode]} {mode.title()} → {icon_p} {value['provider']}/{value['model']} (saved!)")
            save_settings(ctx.guild.id)
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
            embed.set_footer(text="🔄 Reset ke default (saved!)")
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
async def toggle_cmd(ctx: commands.Context):
    settings = get_settings(ctx.guild.id)
    settings["auto_chat"] = not settings["auto_chat"]
    save_settings(ctx.guild.id)
    state = "🟢 ON" if settings["auto_chat"] else "🔴 OFF"
    await ctx.send(f"Auto-chat: {state} (saved! ✅)")

@bot.command(name="channel")
async def channel_cmd(ctx: commands.Context):
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
async def status_cmd(ctx: commands.Context):
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
    
    ch_count = len(settings["enabled_channels"])
    lines.append(f"\nAuto-chat: {auto_chat} | Auto-detect: {auto_detect}")
    lines.append(f"Channels: {ch_count} enabled")
    lines.append(f"\n-# 💾 Settings tersimpan di database (persist after restart)")

    embed = discord.Embed(description="\n".join(lines), color=discord.Color.blue())
    await ctx.send(embed=embed)

@bot.command(name="monitor")
async def monitor_cmd(ctx: commands.Context):
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
async def log_cmd(ctx: commands.Context, n: int = 10):
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
        lines.append(
            f"`{entry['time']}` {status}{fb} {icon} `{entry['provider']}/{entry['model']}` ({entry['latency']:.1f}s)"
        )

    embed = discord.Embed(description="\n".join(lines[:20]), color=discord.Color.blue())
    await ctx.send(embed=embed)

@bot.command(name="reset")
async def reset_cmd(ctx: commands.Context):
    SettingsManager.reset(ctx.guild.id)
    await ctx.send("🔄 Reset ke default berhasil. (saved! ✅)")

# ============================================================
# MEMORY COMMANDS
# ============================================================

@bot.command(name="clear", aliases=["forget", "lupa"])
async def clear_cmd(ctx: commands.Context, scope: str = "channel"):
    from core.database import clear_conversation
    
    if scope == "all":
        clear_conversation(ctx.guild.id)
        await ctx.send("🧹 Semua memory percakapan di server ini sudah dihapus!")
    else:
        clear_conversation(ctx.guild.id, ctx.channel.id)
        await ctx.send(f"🧹 Memory percakapan di {ctx.channel.mention} sudah dihapus!")

@bot.command(name="memory", aliases=["mem"])
async def memory_cmd(ctx: commands.Context):
    from core.database import get_memory_stats, get_conversation, MAX_MEMORY_MESSAGES
    
    stats = get_memory_stats(ctx.guild.id)
    channel_msgs = len(get_conversation(ctx.guild.id, ctx.channel.id))
    
    embed = discord.Embed(title="🧠 Conversation Memory", color=discord.Color.purple())
    embed.add_field(name="Channel Ini", value=f"`{channel_msgs}` / `{MAX_MEMORY_MESSAGES}` pesan", inline=True)
    embed.add_field(name="Server Total", value=f"`{stats['channels']}` channels\n`{stats['total_messages']}` pesan", inline=True)
    embed.add_field(name="Storage", value="💾 Database", inline=True)
    embed.set_footer(text="Gunakan !clear untuk hapus memory")
    await ctx.send(embed=embed)

# ============================================================
# SKILL COMMANDS
# ============================================================

from skills import (
    get_current_time, get_time_difference,
    set_alarm, list_alarms, cancel_alarm,
    get_calendar, days_until,
    get_weather
)

@bot.command(name="time", aliases=["waktu"])
async def time_cmd(ctx: commands.Context, timezone: str = "Asia/Jakarta"):
    result = get_current_time(timezone)
    if result["success"]:
        embed = discord.Embed(
            title="🕐 Waktu Sekarang",
            description=f"**{result['full']}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Jam", value=result['time'], inline=True)
        embed.add_field(name="Tanggal", value=result['date'], inline=True)
        embed.add_field(name="Hari", value=result['day'], inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Error: {result['error']}\n💡 Timezone valid: `Asia/Jakarta`, `America/New_York`, `Europe/London`")

@bot.command(name="alarm")
async def alarm_cmd(ctx: commands.Context, minutes: int, *, message: str = "⏰ Alarm!"):
    if minutes < 1 or minutes > 1440:
        await ctx.send("❌ Alarm hanya bisa 1-1440 menit (1 menit - 24 jam)")
        return
    
    async def alarm_callback(alarm_data):
        user = ctx.guild.get_member(alarm_data["user_id"])
        if user:
            try:
                await ctx.channel.send(f"⏰ {user.mention} **ALARM:** {alarm_data['message']}")
            except:
                pass
    
    result = await set_alarm(ctx.guild.id, ctx.author.id, minutes, message, alarm_callback)
    
    if result["success"]:
        await ctx.send(
            f"⏰ Alarm diset untuk **{minutes} menit** lagi (trigger: {result['trigger_time']})\n"
            f"📝 Pesan: {message}"
        )

@bot.command(name="alarms", aliases=["myalarms"])
async def alarms_cmd(ctx: commands.Context):
    active = list_alarms(ctx.guild.id, ctx.author.id)
    if not active:
        await ctx.send("📭 Kamu tidak punya alarm aktif.")
        return
    
    lines = ["**⏰ Alarm Aktif:**\n"]
    for i, alarm in enumerate(active, 1):
        trigger = alarm['trigger_time'].strftime("%H:%M:%S")
        remaining = (alarm['trigger_time'] - datetime.now()).total_seconds() / 60
        lines.append(f"{i}. `{trigger}` (~{int(remaining)} menit lagi) - {alarm['message']}")
    
    await ctx.send("\n".join(lines))

@bot.command(name="calendar", aliases=["kalender", "cal"])
async def calendar_cmd(ctx: commands.Context, month_input: str = None, year: int = None):
    month = None
    if month_input:
        month = parse_month(month_input)
        if month is None:
            await ctx.send(
                f"❌ Bulan `{month_input}` tidak dikenali!\n"
                f"💡 Contoh: `!calendar februari` atau `!calendar 2` atau `!calendar 12 2026`"
            )
            return
    
    result = get_calendar(year, month)
    if result["success"]:
        embed = discord.Embed(
            title=f"📅 {result['month_name']} {result['year']}",
            description=result["calendar_text"],
            color=discord.Color.green()
        )
        embed.set_footer(text=f"{result['days_in_month']} hari")
        await ctx.send(embed=embed)

@bot.command(name="countdown", aliases=["hitung"])
async def countdown_cmd(ctx: commands.Context, target_date: str):
    result = days_until(target_date)
    if result["success"]:
        if result["is_today"]:
            msg = f"🎉 **Hari ini adalah {target_date}!**"
        elif result["is_past"]:
            msg = f"📅 {target_date} sudah lewat **{abs(result['days_remaining'])} hari** yang lalu"
        else:
            msg = f"⏳ Tinggal **{result['days_remaining']} hari** lagi menuju {target_date}"
        await ctx.send(msg)
    else:
        await ctx.send(f"❌ {result['error']}")

@bot.command(name="weather", aliases=["cuaca"])
async def weather_cmd(ctx: commands.Context, *, city: str = "Jakarta"):
    async with ctx.typing():
        result = await get_weather(city)
    
    if result["success"]:
        embed = discord.Embed(
            title=f"🌤️ Cuaca di {result['city']}",
            description=f"**{result['description']}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="🌡️ Suhu", value=f"{result['temp']}°C", inline=True)
        embed.add_field(name="💨 Terasa", value=f"{result['feels_like']}°C", inline=True)
        embed.add_field(name="💧 Kelembapan", value=f"{result['humidity']}%", inline=True)
        embed.add_field(name="🌬️ Angin", value=f"{result['wind_speed']} km/h", inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ {result['error']}")

# ============================================================
# RUN — MUST BE LAST!
# ============================================================

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        log.error("DISCORD_TOKEN not found in .env")
        exit(1)
    log.info("Starting bot...")
    bot.run(DISCORD_TOKEN)
