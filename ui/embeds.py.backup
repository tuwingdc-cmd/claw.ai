"""
All-in-One Settings UI
Fixed: persistent views, proper deferred interactions
"""

import discord
from discord.ui import View, Select, Button, select, button
from discord import SelectOption, Interaction, Embed
from typing import Dict, Callable, Optional, List
import logging

from config import PROVIDERS, FALLBACK_CHAINS, list_available_providers

log = logging.getLogger(__name__)

# ============================================================
# SETTINGS PANEL EMBED
# ============================================================

def create_settings_panel(
    settings: Dict,
    provider_icons: Dict,
    search_icons: Dict,
    mode_icons: Dict
) -> Embed:
    """Create the all-in-one settings embed"""

    embed = Embed(title="⚙️ Settings", color=discord.Color.blue())
    profiles = settings["profiles"]
    active = settings["active_mode"]

    lines = []
    for mode in ["normal", "reasoning", "search"]:
        p = profiles[mode]
        mi = mode_icons.get(mode, "📦")
        pi = provider_icons.get(p["provider"], "📦")
        marker = " 📌" if mode == active else ""
        line = f"{mi} **{mode.title()}{marker}** : {pi} `{p['provider']}` → `{p['model']}`"
        if mode == "search":
            si = search_icons.get(p.get("engine", "duckduckgo"), "🔍")
            line += f" + {si} `{p.get('engine', 'duckduckgo')}`"
            
            # Show if model has built-in grounding
            from core.handler import is_grounding_model
            if is_grounding_model(p["provider"], p["model"]):
                line += " *(built-in search)*"
            else:
                line += " *(manual search)*"
        lines.append(line)

    embed.add_field(name="Mode Profiles", value="\n".join(lines), inline=False)

    auto_chat = "🟢 ON" if settings.get("auto_chat") else "🔴 OFF"
    auto_detect = "🟢 ON" if settings.get("auto_detect") else "🔴 OFF"
    embed.add_field(
        name="Toggles",
        value=f"Auto-detect: {auto_detect}  |  Auto-chat: {auto_chat}",
        inline=False
    )

    # Search info
    embed.add_field(
        name="🔍 Search Info",
        value=(
            "**Auto-detect ON** → bot otomatis search kalau deteksi pertanyaan real-time\n"
            "**Model grounding** (gemini-search/perplexity) → search built-in\n"
            "**Model biasa** → DuckDuckGo search + LLM summarize"
        ),
        inline=False
    )

    return embed

# ============================================================
# MAIN SETTINGS VIEW
# ============================================================

class SettingsView(View):
    """Main settings: mode selector + toggles"""

    def __init__(self, settings, callback, provider_icons, search_icons, mode_icons, timeout=300):
        super().__init__(timeout=timeout)
        self.settings = settings
        self.callback = callback
        self.pi = provider_icons
        self.si = search_icons
        self.mi = mode_icons

        # Row 0: Mode selector
        self.add_item(ModeDropdown(settings, self._on_mode_select, mode_icons, provider_icons))

    async def _on_mode_select(self, interaction: Interaction, mode: str):
        """When mode is selected, show config for that mode"""
        self.settings["active_mode"] = mode
        profile = self.settings["profiles"][mode]
        
        embed = create_mode_config_embed(mode, profile, self.mi, self.pi, self.si)
        view = ModeConfigView(self.settings, mode, self.callback, self.mi, self.pi, self.si)
        await interaction.response.edit_message(embed=embed, view=view)

    @button(label="Auto-Detect", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def toggle_detect(self, interaction: Interaction, btn: Button):
        self.settings["auto_detect"] = not self.settings.get("auto_detect", False)
        await self.callback(interaction, "auto_detect", self.settings["auto_detect"])

    @button(label="Auto-Chat", style=discord.ButtonStyle.secondary, emoji="💬", row=1)
    async def toggle_chat(self, interaction: Interaction, btn: Button):
        self.settings["auto_chat"] = not self.settings.get("auto_chat", False)
        await self.callback(interaction, "auto_chat", self.settings["auto_chat"])

    @button(label="Monitor", style=discord.ButtonStyle.success, emoji="📊", row=1)
    async def monitor(self, interaction: Interaction, btn: Button):
        available = list_available_providers()
        lines = []
        for name, provider in PROVIDERS.items():
            icon = self.pi.get(name, "📦")
            status = "🟢" if name in available else "⚪"
            lines.append(f"{status} {icon} **{provider.name}** • `{provider.rate_limit}`")

        embed = Embed(title="📊 Provider Health", description="\n".join(lines), color=discord.Color.blue())
        view = BackToMainView(self.settings, self.callback, self.pi, self.si, self.mi)
        await interaction.response.edit_message(embed=embed, view=view)

    @button(label="Reset", style=discord.ButtonStyle.danger, emoji="🔄", row=1)
    async def reset(self, interaction: Interaction, btn: Button):
        await self.callback(interaction, "reset", True)

# ============================================================
# MODE DROPDOWN
# ============================================================

class ModeDropdown(Select):
    def __init__(self, settings, callback, mode_icons, provider_icons):
        self.cb = callback
        active = settings.get("active_mode", "normal")
        profiles = settings.get("profiles", {})

        options = []
        for mode_key, label, emoji, desc in [
            ("normal", "Normal Chat", "💬", "Chat biasa — fast response"),
            ("reasoning", "Reasoning", "🧠", "Deep thinking — step by step"),
            ("search", "Search", "🔍", "Web search — real-time info"),
        ]:
            p = profiles.get(mode_key, {})
            pi = provider_icons.get(p.get("provider", ""), "")
            current_info = f"Now: {pi} {p.get('provider', '?')}/{p.get('model', '?')}"
            
            options.append(SelectOption(
                label=label,
                value=mode_key,
                emoji=emoji,
                description=current_info[:100],
                default=mode_key == active
            ))

        super().__init__(placeholder="Pilih mode untuk dikonfigurasi...", options=options, row=0)

    async def callback(self, interaction: Interaction):
        await self.cb(interaction, self.values[0])

# ============================================================
# MODE CONFIG EMBED
# ============================================================

def create_mode_config_embed(mode, profile, mode_icons, provider_icons, search_icons) -> Embed:
    mi = mode_icons.get(mode, "📦")
    pi = provider_icons.get(profile["provider"], "📦")

    embed = Embed(
        title=f"{mi} Configure {mode.title()}",
        color=discord.Color.blue()
    )

    current = f"{pi} `{profile['provider']}` → `{profile['model']}`"
    
    if mode == "search":
        si = search_icons.get(profile.get("engine", "duckduckgo"), "🦆")
        current += f"\n{si} Search engine: `{profile.get('engine', 'duckduckgo')}`"
        
        from core.handler import is_grounding_model
        if is_grounding_model(profile["provider"], profile["model"]):
            current += "\n✅ **Built-in grounding** — search otomatis dari model"
        else:
            current += "\n🔧 **Manual search** — DuckDuckGo + LLM summarize"

    embed.add_field(name="Current", value=current, inline=False)

    # Fallback chain
    chain = FALLBACK_CHAINS.get(mode, FALLBACK_CHAINS["normal"])
    fb_lines = []
    for i, (prov, model) in enumerate(chain[:5], 1):
        fi = provider_icons.get(prov, "📦")
        model_str = model or prov
        fb_lines.append(f"{i}. {fi} `{prov}` → `{model_str}`")

    embed.add_field(name="Fallback Chain", value="\n".join(fb_lines), inline=False)

    if mode == "search":
        embed.add_field(
            name="💡 Tips",
            value=(
                "**Model grounding** (otomatis search):\n"
                "• 🐝 Pollinations → `gemini-search`\n"
                "• 🐝 Pollinations → `perplexity-fast`\n"
                "• 🐝 Pollinations → `perplexity-reasoning`\n\n"
                "**Model biasa** (manual search):\n"
                "• 🦆 DuckDuckGo cari info → LLM rangkum"
            ),
            inline=False
        )

    embed.set_footer(text="Step 1: Pilih Provider → Step 2: Pilih Model → Save")
    return embed

# ============================================================
# MODE CONFIG VIEW (Provider + Model + Save/Test/Back)
# ============================================================

class ModeConfigView(View):
    """Configure provider + model for a specific mode"""

    def __init__(self, settings, mode, callback, mode_icons, provider_icons, search_icons, timeout=300):
        super().__init__(timeout=timeout)
        self.settings = settings
        self.mode = mode
        self.cb = callback
        self.mi = mode_icons
        self.pi = provider_icons
        self.si = search_icons
        
        self._selected_provider = settings["profiles"][mode]["provider"]
        self._selected_model = settings["profiles"][mode]["model"]

        # Row 0: Provider dropdown
        self.add_item(ProviderDropdown(
            settings, mode, provider_icons, self._on_provider_select
        ))

        # Row 1: Model dropdown
        self.add_item(ModelDropdown(
            self._selected_provider, self._selected_model, mode, self._on_model_select
        ))

    async def _on_provider_select(self, interaction: Interaction, provider_name: str):
        """Provider selected → refresh model list"""
        self._selected_provider = provider_name
        
        # Auto-select first model
        provider = PROVIDERS.get(provider_name)
        if provider and provider.models:
            # Try to find a model that matches the mode
            for m in provider.models:
                if self.mode in m.modes:
                    self._selected_model = m.id
                    break
            else:
                self._selected_model = provider.models[0].id

        # Update profile temporarily
        self.settings["profiles"][self.mode]["provider"] = provider_name
        self.settings["profiles"][self.mode]["model"] = self._selected_model

        # Rebuild embed + view with new model dropdown
        profile = self.settings["profiles"][self.mode]
        embed = create_mode_config_embed(self.mode, profile, self.mi, self.pi, self.si)
        view = ModeConfigView(self.settings, self.mode, self.cb, self.mi, self.pi, self.si)
        await interaction.response.edit_message(embed=embed, view=view)

    async def _on_model_select(self, interaction: Interaction, model_id: str):
        """Model selected → update display"""
        self._selected_model = model_id
        self.settings["profiles"][self.mode]["model"] = model_id

        profile = self.settings["profiles"][self.mode]
        embed = create_mode_config_embed(self.mode, profile, self.mi, self.pi, self.si)
        
        # Rebuild view to keep dropdowns alive
        view = ModeConfigView(self.settings, self.mode, self.cb, self.mi, self.pi, self.si)
        await interaction.response.edit_message(embed=embed, view=view)

    @button(label="Save", style=discord.ButtonStyle.success, emoji="✅", row=2)
    async def save_btn(self, interaction: Interaction, btn: Button):
        value = {
            "mode": self.mode,
            "provider": self._selected_provider,
            "model": self._selected_model,
        }
        if self.mode == "search":
            value["engine"] = self.settings["profiles"]["search"].get("engine", "duckduckgo")
        await self.cb(interaction, "save_profile", value)

    @button(label="Test", style=discord.ButtonStyle.primary, emoji="🧪", row=2)
    async def test_btn(self, interaction: Interaction, btn: Button):
        """Test model with a simple ping"""
        # Defer to avoid timeout (test bisa lambat)
        await interaction.response.defer()
        
        from core.providers import ProviderFactory
        from config import API_KEYS

        provider = ProviderFactory.get(self._selected_provider, API_KEYS)
        if not provider:
            embed = create_mode_config_embed(
                self.mode, self.settings["profiles"][self.mode],
                self.mi, self.pi, self.si
            )
            icon = self.pi.get(self._selected_provider, "📦")
            embed.set_footer(text=f"❌ {icon} {self._selected_provider}: no API key")
            view = ModeConfigView(self.settings, self.mode, self.cb, self.mi, self.pi, self.si)
            await interaction.followup.edit_message(
                message_id=interaction.message.id, embed=embed, view=view
            )
            return

        messages = [{"role": "user", "content": "Respond with only: OK"}]
        result = await provider.chat(messages, self._selected_model, max_tokens=10)

        icon = self.pi.get(self._selected_provider, "📦")
        
        embed = create_mode_config_embed(
            self.mode, self.settings["profiles"][self.mode],
            self.mi, self.pi, self.si
        )
        
        if result.success:
            embed.set_footer(
                text=f"✅ Test passed: {icon} {self._selected_provider}/{self._selected_model} ({result.latency:.1f}s)"
            )
        else:
            embed.set_footer(
                text=f"❌ Test failed: {icon} {self._selected_provider}/{self._selected_model} — {result.error}"
            )

        view = ModeConfigView(self.settings, self.mode, self.cb, self.mi, self.pi, self.si)
        await interaction.followup.edit_message(
            message_id=interaction.message.id, embed=embed, view=view
        )

    @button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def back_btn(self, interaction: Interaction, btn: Button):
        await self.cb(interaction, "back", None)

# ============================================================
# PROVIDER DROPDOWN
# ============================================================

class ProviderDropdown(Select):
    def __init__(self, settings, mode, provider_icons, callback):
        self.cb = callback
        current = settings["profiles"][mode]["provider"]
        available = list_available_providers()

        options = []
        for name, provider in PROVIDERS.items():
            icon = provider_icons.get(name, "📦")
            
            if name not in available:
                status = "✗ no key"
            else:
                status = "✓ ready"

            # Count models for this mode
            mode_models = [m for m in provider.models if mode in m.modes]
            all_models = len(provider.models)
            
            desc = f"{status} • {len(mode_models)}/{all_models} models • {provider.rate_limit}"

            options.append(SelectOption(
                label=provider.name,
                value=name,
                description=desc[:100],
                emoji=icon,
                default=name == current
            ))

        super().__init__(
            placeholder="Step 1: Pilih Provider",
            options=options[:25],
            row=0,
            custom_id=f"provider_select_{mode}"
        )

    async def callback(self, interaction: Interaction):
        await self.cb(interaction, self.values[0])

# ============================================================
# MODEL DROPDOWN
# ============================================================

class ModelDropdown(Select):
    def __init__(self, provider_name, current_model, mode, callback):
        self.cb = callback
        provider = PROVIDERS.get(provider_name)
        options = []

        if provider:
            # Show mode-specific models first, then others
            mode_models = [m for m in provider.models if mode in m.modes]
            other_models = [m for m in provider.models if mode not in m.modes]
            
            for model in mode_models:
                badges = []
                if "reasoning" in model.modes:
                    badges.append("🧠")
                if "search" in model.modes:
                    badges.append("🔍")
                if model.vision:
                    badges.append("👁️")
                if model.tools:
                    badges.append("🔧")
                badge = " ".join(badges)

                options.append(SelectOption(
                    label=f"★ {model.name}"[:100],
                    value=model.id,
                    description=f"{model.id} {badge}"[:100],
                    default=model.id == current_model
                ))

            # Separator: other models
            for model in other_models:
                options.append(SelectOption(
                    label=model.name[:100],
                    value=model.id,
                    description=model.id[:100],
                    default=model.id == current_model
                ))

        if not options:
            options.append(SelectOption(label="No models", value="none"))

        super().__init__(
            placeholder="Step 2: Pilih Model",
            options=options[:25],
            row=1,
            custom_id=f"model_select_{provider_name}_{mode}"
        )

    async def callback(self, interaction: Interaction):
        if self.values[0] != "none":
            await self.cb(interaction, self.values[0])

# ============================================================
# BACK TO MAIN VIEW
# ============================================================

class BackToMainView(View):
    def __init__(self, settings, callback, pi, si, mi, timeout=120):
        super().__init__(timeout=timeout)
        self.settings = settings
        self.cb = callback
        self.pi = pi
        self.si = si
        self.mi = mi

    @button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def back(self, interaction: Interaction, btn: Button):
        await self.cb(interaction, "back", None)
