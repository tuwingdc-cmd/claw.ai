"""
All-in-One Settings UI
Single !set command → Mode + Provider + Model in one panel
"""

import discord
from discord.ui import View, Select, Button, select, button
from discord import SelectOption, Interaction, Embed
from typing import Dict, Callable, Optional
import logging

from config import PROVIDERS, FALLBACK_CHAINS, list_available_providers

log = logging.getLogger(__name__)

# ============================================================
# MAIN SETTINGS PANEL EMBED
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
        lines.append(line)

    embed.add_field(name="Mode Profiles", value="\n".join(lines), inline=False)

    auto_chat = "🟢 ON" if settings.get("auto_chat") else "🔴 OFF"
    auto_detect = "🟢 ON" if settings.get("auto_detect") else "🔴 OFF"
    embed.add_field(
        name="Toggles",
        value=f"Auto-detect: {auto_detect}  |  Auto-chat: {auto_chat}",
        inline=False
    )

    return embed

# ============================================================
# MAIN SETTINGS VIEW (Buttons + Mode Select)
# ============================================================

class SettingsView(View):
    """Main settings panel: select mode, then configure"""

    def __init__(
        self,
        settings: Dict,
        callback: Callable,
        provider_icons: Dict,
        search_icons: Dict,
        mode_icons: Dict,
        timeout: int = 300
    ):
        super().__init__(timeout=timeout)
        self.settings = settings
        self.callback = callback
        self.pi = provider_icons
        self.si = search_icons
        self.mi = mode_icons

        # Row 0: Mode selector dropdown
        self.add_item(ModeDropdown(settings, callback, mode_icons))

    # Row 1 buttons
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
        view = BackOnlyView(self.settings, self.callback, self.pi, self.si, self.mi)
        await interaction.response.edit_message(embed=embed, view=view)

    @button(label="Reset", style=discord.ButtonStyle.danger, emoji="🔄", row=1)
    async def reset(self, interaction: Interaction, btn: Button):
        await self.callback(interaction, "reset", True)

# ============================================================
# MODE DROPDOWN (Step 1: Pick which mode to configure)
# ============================================================

class ModeDropdown(Select):
    """Select which mode to configure"""

    def __init__(self, settings: Dict, callback: Callable, mode_icons: Dict):
        self.settings = settings
        self.cb = callback
        self.mi = mode_icons

        active = settings.get("active_mode", "normal")
        options = [
            SelectOption(label="Normal Chat", value="normal", emoji="💬",
                         description="Configure normal chat provider & model",
                         default=active == "normal"),
            SelectOption(label="Reasoning", value="reasoning", emoji="🧠",
                         description="Configure reasoning provider & model",
                         default=active == "reasoning"),
            SelectOption(label="Search", value="search", emoji="🔍",
                         description="Configure search engine & summarizer",
                         default=active == "search"),
        ]
        super().__init__(placeholder="Select mode to configure...", options=options, row=0)

    async def callback(self, interaction: Interaction):
        mode = self.values[0]
        self.settings["active_mode"] = mode

        profile = self.settings["profiles"][mode]
        embed = _create_mode_config_embed(mode, profile, self.mi)
        view = ModeConfigView(self.settings, mode, self.cb, self.mi)
        await interaction.response.edit_message(embed=embed, view=view)

# ============================================================
# MODE CONFIG VIEW (Step 2: Provider + Model for chosen mode)
# ============================================================

def _create_mode_config_embed(mode: str, profile: Dict, mode_icons: Dict) -> Embed:
    """Embed for configuring a specific mode"""
    from main import PROVIDER_ICONS, SEARCH_ICONS

    mi = mode_icons.get(mode, "📦")
    pi = PROVIDER_ICONS.get(profile["provider"], "📦")

    embed = Embed(
        title=f"{mi} Configure {mode.title()}",
        color=discord.Color.blue()
    )

    current = f"{pi} `{profile['provider']}` → `{profile['model']}`"
    if mode == "search":
        si = SEARCH_ICONS.get(profile.get("engine", "duckduckgo"), "🦆")
        current += f"\n{si} Search: `{profile.get('engine', 'duckduckgo')}`"

    embed.add_field(name="Current", value=current, inline=False)

    # Show fallback chain
    chain = FALLBACK_CHAINS.get(mode, FALLBACK_CHAINS["normal"])
    fb_lines = []
    for i, (prov, model) in enumerate(chain[:5], 1):
        fi = PROVIDER_ICONS.get(prov, "📦")
        model_str = model or prov
        fb_lines.append(f"{i}. {fi} `{prov}` → `{model_str}`")

    embed.add_field(name="Fallback Chain", value="\n".join(fb_lines), inline=False)
    embed.set_footer(text="Step 1: Select Provider → Step 2: Select Model")

    return embed


class ModeConfigView(View):
    """Provider + Model selection for a mode"""

    def __init__(self, settings: Dict, mode: str, callback: Callable, mode_icons: Dict, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.settings = settings
        self.mode = mode
        self.cb = callback
        self.mi = mode_icons
        self._selected_provider = settings["profiles"][mode]["provider"]
        self._selected_model = settings["profiles"][mode]["model"]

        # Row 0: Provider dropdown
        self.add_item(ProviderDropdown(settings, mode, self._on_provider))

        # Row 1: Model dropdown (for current provider)
        self.add_item(ModelDropdown(self._selected_provider, self._selected_model, mode, self._on_model))

    async def _on_provider(self, interaction: Interaction, provider_name: str):
        """When provider is selected, refresh model dropdown"""
        self._selected_provider = provider_name
        provider = PROVIDERS.get(provider_name)
        if provider and provider.models:
            self._selected_model = provider.models[0].id

        # Rebuild view with new model dropdown
        profile = self.settings["profiles"][self.mode]
        profile["provider"] = provider_name
        profile["model"] = self._selected_model

        embed = _create_mode_config_embed(self.mode, profile, self.mi)
        view = ModeConfigView(self.settings, self.mode, self.cb, self.mi)
        await interaction.response.edit_message(embed=embed, view=view)

    async def _on_model(self, interaction: Interaction, model_id: str):
        """When model is selected"""
        self._selected_model = model_id
        self.settings["profiles"][self.mode]["model"] = model_id

        profile = self.settings["profiles"][self.mode]
        embed = _create_mode_config_embed(self.mode, profile, self.mi)
        embed.set_footer(text=f"Model selected: {model_id} — click Save to confirm")
        view = ModeConfigView(self.settings, self.mode, self.cb, self.mi)
        await interaction.response.edit_message(embed=embed, view=view)

    # Row 2 buttons
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
        """Test current provider/model with a simple prompt"""
        from core.providers import ProviderFactory
        from config import API_KEYS
        
        provider = ProviderFactory.get(self._selected_provider, API_KEYS)
        if not provider:
            await self.cb(interaction, "test_result", {
                "success": False,
                "msg": f"❌ {self._selected_provider}: no API key"
            })
            return

        messages = [{"role": "user", "content": "Respond with only: OK"}]
        result = await provider.chat(messages, self._selected_model, max_tokens=10)

        from main import PROVIDER_ICONS
        icon = PROVIDER_ICONS.get(self._selected_provider, "📦")

        if result.success:
            await self.cb(interaction, "test_result", {
                "success": True,
                "msg": f"✅ {icon} {self._selected_provider}/{self._selected_model} — OK ({result.latency:.1f}s)"
            })
        else:
            await self.cb(interaction, "test_result", {
                "success": False,
                "msg": f"❌ {icon} {self._selected_provider}/{self._selected_model} — {result.error}"
            })

    @button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def back_btn(self, interaction: Interaction, btn: Button):
        await self.cb(interaction, "back", None)

# ============================================================
# PROVIDER DROPDOWN
# ============================================================

class ProviderDropdown(Select):
    """Select provider for a mode"""

    def __init__(self, settings: Dict, mode: str, callback: Callable):
        self.cb = callback

        from main import PROVIDER_ICONS
        current = settings["profiles"][mode]["provider"]
        available = list_available_providers()

        options = []
        for name, provider in PROVIDERS.items():
            icon = PROVIDER_ICONS.get(name, "📦")
            status = "✓" if name in available else "✗ no key"

            # Count models that support this mode
            mode_models = [m for m in provider.models if mode in m.modes]
            all_models = len(provider.models)

            options.append(SelectOption(
                label=f"{provider.name} ({len(mode_models)}/{all_models} models)",
                value=name,
                description=f"{status} • {provider.rate_limit}",
                emoji=icon,
                default=name == current
            ))

        super().__init__(placeholder="Step 1: Select Provider", options=options[:25], row=0)

    async def callback(self, interaction: Interaction):
        await self.cb(interaction, self.values[0])

# ============================================================
# MODEL DROPDOWN
# ============================================================

class ModelDropdown(Select):
    """Select model for chosen provider"""

    def __init__(self, provider_name: str, current_model: str, mode: str, callback: Callable):
        self.cb = callback

        provider = PROVIDERS.get(provider_name)
        options = []

        if provider:
            for model in provider.models:
                # Badge
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

                label = model.name[:95]
                desc = f"{model.id[:90]} {badge}"

                options.append(SelectOption(
                    label=label,
                    value=model.id,
                    description=desc,
                    default=model.id == current_model
                ))

        if not options:
            options.append(SelectOption(label="No models", value="none", description="N/A"))

        super().__init__(placeholder="Step 2: Select Model", options=options[:25], row=1)

    async def callback(self, interaction: Interaction):
        if self.values[0] != "none":
            await self.cb(interaction, self.values[0])

# ============================================================
# BACK ONLY VIEW (for monitor sub-page)
# ============================================================

class BackOnlyView(View):
    """Simple view with just a Back button"""

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
