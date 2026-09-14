from __future__ import annotations

import logging

import discord
import httpx

from bot.config import settings

logger = logging.getLogger(__name__)


class LanguageSelection:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self.base = settings.backend_url.rstrip("/") + "/api/v1/internal/plugin-first-introduction"
        self.headers = {"X-ShieldNet-Service-Token": settings.internal_service_token}

    async def configuration(self, guild_id: int) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base}/guilds/{guild_id}/configuration", headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def begin(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Use this command on your server.", ephemeral=True)
            return
        config = await self.configuration(interaction.guild.id)
        if not config["enabled"] or not config["languages"]:
            await interaction.response.send_message("Language selection is not configured here.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Choose your language. You can change it later.",
            view=LanguageChoices(self, interaction.user.id, config["languages"]),
            ephemeral=True,
        )

    async def choose(self, interaction: discord.Interaction, code: str) -> str:
        guild = interaction.guild
        if guild is None:
            raise ValueError("Use language selection on your server")
        config = await self.configuration(guild.id)
        languages = {item["code"]: item["name"] for item in config["languages"]}
        if not config["enabled"] or code not in languages:
            raise ValueError("This language is no longer available")
        role_ids = config["language_roles"]
        selected_id = role_ids.get(code)
        if not selected_id:
            raise ValueError("The selected language has no role configured")
        selected = guild.get_role(int(selected_id))
        if selected is None:
            raise ValueError("The selected language role no longer exists")
        bot_member = guild.me
        if bot_member is None or selected >= bot_member.top_role:
            raise ValueError("Move the bot role above the language roles")
        member = guild.get_member(interaction.user.id) or await guild.fetch_member(interaction.user.id)
        old_roles = [role for role in member.roles if role.id != selected.id and str(role.id) in role_ids.values()]
        if any(role >= bot_member.top_role for role in old_roles):
            raise ValueError("Move the bot role above the language roles")
        if selected not in member.roles:
            await member.add_roles(selected, reason="GuildConsole language selection")
        if old_roles:
            await member.remove_roles(*old_roles, reason="GuildConsole language selection changed")
        return languages[code]


class LanguagePanel(discord.ui.View):
    def __init__(self, plugin: LanguageSelection) -> None:
        super().__init__(timeout=None)
        self.plugin = plugin

    @discord.ui.button(label="Choose language", style=discord.ButtonStyle.primary,
                       custom_id="guildconsole:language-selection:open")
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        try:
            await self.plugin.begin(interaction)
        except Exception:
            logger.exception("Language selection could not open guild=%s", interaction.guild_id)
            if not interaction.response.is_done():
                await interaction.response.send_message("Could not load languages. Try again later.", ephemeral=True)


class LanguageSelect(discord.ui.Select):
    def __init__(self, languages: list[dict]) -> None:
        super().__init__(
            placeholder="Choose your language", min_values=1, max_values=1,
            options=[discord.SelectOption(label=item["name"][:100], value=item["code"])
                     for item in languages[:25]],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("This selection belongs to another member.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            name = await self.view.plugin.choose(interaction, self.values[0])
            await interaction.followup.send(f"Language set to **{name}**.", ephemeral=True)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except Exception:
            logger.exception("Could not assign language guild=%s user=%s", interaction.guild_id, interaction.user.id)
            await interaction.followup.send("Could not assign the language role. Try again later.", ephemeral=True)


class LanguageChoices(discord.ui.View):
    def __init__(self, plugin: LanguageSelection, user_id: int, languages: list[dict]) -> None:
        super().__init__(timeout=300)
        self.plugin = plugin
        self.user_id = user_id
        self.add_item(LanguageSelect(languages))
