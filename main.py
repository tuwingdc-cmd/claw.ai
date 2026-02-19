"""
Discord AI Bot - Entry Point
Multi-provider AI with fallback system
"""

import discord
from discord.ext import commands
import asyncio
import logging
from config import (
    DISCORD_TOKEN,
    DISCORD_PREFIX,
    DEFAULTS,
    PROVIDERS,
    list_available_providers
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix=DISCORD_PREFIX,
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
# IN-MEMORY SETTINGS (replaced by DB later)
# ============================================================

guild_settings = {}

def get_settings(guild_id: int) -> dict:
    """Get or create guild settings with mode profiles"""
    if guild_id not in guild_settings:
        guild_settings[guild_id] = {
            # Mode profiles — each mode has its own provider+model
            "profiles": {
                "normal": {
                    "provider": "groq",
                    "model": "llama-3.3-70b-versatile",
                },
                "reasoning": {
                    "provider": "groq",
                    "model": "deepseek-r1-distill-llama-70b",
                },
                "search": {
                    "provider": "groq",
                    "model": "llama-3.3-70b-versatile",
                    "engine": "duckduckgo",
                },
            },
            "active_mode": "normal",
            "auto_chat": False,
            "auto_detect": False,
            "enabled_channels": [],
        }
    return guild_settings[guild_id]

def get_active_profile(guild_id: int) -> dict:
    """Get current active mode profile"""
    s = get_settings(guild_id)
    mode = s["active_mode"]
    return s["profiles"][mode]

# ============================================================
# EVENTS
# ============================================================

@bot.event
async def on_ready():
    log.info(f"Bot ready: {bot.user.name} ({bot.user.id})")
    log.info(f"Servers: {len(bot.guilds)}")
    log.info(f"Providers: {list_available_providers()}")
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

    # Determine if bot should respond
    should_respond = False

    if settings["auto_chat"]:
        if message.channel.id in settings["enabled_channels"]:
            should_respond = True

    if bot.user in message.mentions:
        should_respond = True

    if not should_respond:
        return

    # Clean content
    content = message.content.replace(f"<@{bot.user.id}>", "").strip()
    if not content:
        content = "Hello!"

    async with message.channel.typing():
            from core.handler import handle_message
            # Inject guild_id ke settings supaya log bisa track
            settings["guild_id"] = message.guild.id
            result = await handle_message(content, settings)
        # result = { "text": "...", "fallback_note": "..." or None }
        response_text = result["text"]
        fallback_note = result.get("fallback_note")

        # Append fallback notice if any (plaintext, small)
        if fallback_note:
            response_text += f"\n\n-# {fallback_note}"

        # Split if too long (plaintext, no embed)
        if len(response_text) > 2000:
            chunks = _split_message(response_text)
            for chunk in chunks:
                await message.reply(chunk, mention_author=False)
        else:
            await message.reply(response_text, mention_author=False)

# ============================================================
# COMMANDS
# ============================================================

@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    """Show commands"""
    p = DISCORD_PREFIX
    embed = discord.Embed(
        title="🤖 AI Bot",
        color=discord.Color.blue(),
        description=(
            f"**Commands:**\n"
            f"`{p}set` — Konfigurasi mode, provider, dan model\n"
            f"`{p}toggle` — Toggle auto-chat ON/OFF\n"
            f"`{p}channel` — Enable/disable channel untuk auto-chat\n"
            f"`{p}status` — Lihat konfigurasi saat ini\n"
            f"`{p}monitor` — Health dashboard provider\n"
            f"`{p}log [n]` — Lihat n request log terakhir\n"
            f"`{p}reset` — Reset ke default\n\n"
            f"**Chat:**\n"
            f"Mention <@{bot.user.id}> untuk chat\n"
            f"Atau aktifkan auto-chat di channel tertentu"
        )
    )
    await ctx.send(embed=embed)

# ============================================================
# !SET — ALL-IN-ONE SETTINGS
# ============================================================

@bot.command(name="set")
async def set_cmd(ctx: commands.Context):
    """All-in-one settings panel"""
    settings = get_settings(ctx.guild.id)

    from ui.embeds import create_settings_panel, SettingsView

    embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)

    async def on_update(interaction: discord.Interaction, key: str, value):
        """Callback when setting changes"""
        nonlocal settings

        if key == "save_profile":
            # value = {"mode": ..., "provider": ..., "model": ...}
            mode = value["mode"]
            settings["profiles"][mode]["provider"] = value["provider"]
            settings["profiles"][mode]["model"] = value["model"]
            if mode == "search" and "engine" in value:
                settings["profiles"][mode]["engine"] = value["engine"]

            icon_p = PROVIDER_ICONS.get(value["provider"], "📦")
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            embed.set_footer(text=f"✅ {MODE_ICONS[mode]} {mode.title()} → {icon_p} {value['provider']}/{value['model']}")
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)

        elif key == "auto_chat":
            settings["auto_chat"] = value
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)

        elif key == "auto_detect":
            settings["auto_detect"] = value
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)

        elif key == "active_mode":
            settings["active_mode"] = value
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)

        elif key == "test_result":
            # value = {"success": bool, "msg": str}
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            embed.set_footer(text=value["msg"])
            view = SettingsView(settings, on_update, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            await interaction.response.edit_message(embed=embed, view=view)

        elif key == "reset":
            settings.update({
                "profiles": {
                    "normal": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
                    "reasoning": {"provider": "groq", "model": "deepseek-r1-distill-llama-70b"},
                    "search": {"provider": "groq", "model": "llama-3.3-70b-versatile", "engine": "duckduckgo"},
                },
                "active_mode": "normal",
                "auto_chat": False,
                "auto_detect": False,
            })
            embed = create_settings_panel(settings, PROVIDER_ICONS, SEARCH_ICONS, MODE_ICONS)
            embed.set_footer(text="🔄 Reset ke default")
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
    state = "🟢 ON" if settings["auto_chat"] else "🔴 OFF"
    await ctx.send(f"Auto-chat: {state}")

@bot.command(name="channel")
async def channel_cmd(ctx: commands.Context):
    settings = get_settings(ctx.guild.id)
    ch = ctx.channel.id
    if ch in settings["enabled_channels"]:
        settings["enabled_channels"].remove(ch)
        await ctx.send(f"🔴 {ctx.channel.mention} dihapus dari auto-chat")
    else:
        settings["enabled_channels"].append(ch)
        await ctx.send(f"🟢 {ctx.channel.mention} ditambahkan ke auto-chat")

@bot.command(name="status")
async def status_cmd(ctx: commands.Context):
    settings = get_settings(ctx.guild.id)
    profiles = settings["profiles"]

    lines = ["**⚙️ Current Configuration**\n"]
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
    lines.append(f"\nAuto-chat: {auto_chat} | Auto-detect: {auto_detect}")

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
    settings = get_settings(ctx.guild.id)
    settings.update({
        "profiles": {
            "normal": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
            "reasoning": {"provider": "groq", "model": "deepseek-r1-distill-llama-70b"},
            "search": {"provider": "groq", "model": "llama-3.3-70b-versatile", "engine": "duckduckgo"},
        },
        "active_mode": "normal",
        "auto_chat": False,
        "auto_detect": False,
        "enabled_channels": [],
    })
    await ctx.send("🔄 Reset ke default berhasil.")

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
# RUN
# ============================================================

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        log.error("DISCORD_TOKEN not found in .env")
        exit(1)
    log.info("Starting bot...")
    bot.run(DISCORD_TOKEN)
