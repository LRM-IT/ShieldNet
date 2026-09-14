from __future__ import annotations

import logging

import discord
import httpx

from bot.config import settings

logger = logging.getLogger(__name__)


class FirstIntroduction:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self.base = settings.backend_url.rstrip("/") + "/api/v1/internal/plugin-first-introduction"
        self.headers = {"X-ShieldNet-Service-Token": settings.internal_service_token}

    async def get(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(self.base + path, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.base + path, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def configuration(self, guild_id: int) -> dict:
        return await self.get(f"/guilds/{guild_id}/configuration")

    async def completed(self, guild_id: int, user_id: int) -> bool:
        return bool((await self.get(f"/guilds/{guild_id}/members/{user_id}"))["completed"])

    async def prompt_on_join(self, member: discord.Member) -> None:
        if member.bot or member.pending:
            return
        config = await self.configuration(member.guild.id)
        if not config["enabled"] or not config["server_numbers"] or not config["languages"]:
            return
        if await self.completed(member.guild.id, member.id):
            return
        embed = discord.Embed(
            title="First introduction",
            description=str(config["prompt_text"]),
            colour=discord.Colour.teal(),
        )
        embed.set_footer(text=f"guild:{member.guild.id}")
        view = IntroStartView(self)
        mode = config.get("delivery_mode", "dm_with_fallback")
        if mode != "channel":
            try:
                await member.send(embed=embed, view=view)
                return
            except discord.HTTPException:
                if mode == "dm":
                    logger.info("Introduction DM closed guild=%s user=%s", member.guild.id, member.id)
                    return
        channel_id = config.get("fallback_channel_id")
        channel = member.guild.get_channel(int(channel_id)) if channel_id else None
        if isinstance(channel, discord.TextChannel):
            await channel.send(content=member.mention, embed=embed, view=view,
                               allowed_mentions=discord.AllowedMentions(users=True))
        else:
            logger.warning("Introduction channel unavailable guild=%s", member.guild.id)

    async def begin(self, interaction: discord.Interaction, guild_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            await interaction.response.send_message("Server is unavailable.", ephemeral=True)
            return
        member = guild.get_member(interaction.user.id)
        if member is None:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except discord.HTTPException:
                await interaction.response.send_message("You must be a member of this server.", ephemeral=True)
                return
        config = await self.configuration(guild_id)
        if not config["enabled"]:
            await interaction.response.send_message("Introduction is not enabled on this server.", ephemeral=True)
            return
        if await self.completed(guild_id, member.id):
            await interaction.response.send_message("You have already completed the introduction.", ephemeral=True)
            return
        if not config["languages"] or not config["server_numbers"]:
            await interaction.response.send_message("The introduction is not configured yet.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Choose your language and server number, then continue.",
            view=IntroSelectionsView(self, guild_id, member.id, config),
            ephemeral=interaction.guild is not None,
        )

    async def finish(self, interaction: discord.Interaction, guild_id: int, language: str,
                     server_number: str, alliance: str, nickname: str) -> str:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            raise ValueError("Server is unavailable")
        member = guild.get_member(interaction.user.id) or await guild.fetch_member(interaction.user.id)
        if await self.completed(guild_id, member.id):
            raise ValueError("Introduction was already completed")
        config = await self.configuration(guild_id)
        if not config["enabled"] or language not in {item["code"] for item in config["languages"]}:
            raise ValueError("Language is no longer available")
        if server_number not in config["server_numbers"]:
            raise ValueError("Server number is no longer available")
        role_ids = [config["language_roles"].get(language), config.get("verified_role_id")]
        if not all(role_ids):
            raise ValueError("Roles are not configured")
        roles = [guild.get_role(int(role_id)) for role_id in role_ids]
        if any(role is None for role in roles):
            raise ValueError("A configured role no longer exists")
        bot_member = guild.me
        if bot_member is None or any(role >= bot_member.top_role for role in roles):
            raise ValueError("Move the bot role above the configured roles")
        applied = config["nickname_template"].format(
            server=server_number, alliance=alliance.strip(), nick=nickname.strip()
        ).strip()
        if not 1 <= len(applied) <= 32:
            raise ValueError("The resulting nickname must be 1-32 characters")
        if member == guild.owner or member.top_role >= bot_member.top_role:
            raise ValueError("The bot cannot change this member's nickname")
        added = [role for role in roles if role not in member.roles]
        try:
            if added:
                await member.add_roles(*added, reason="GuildConsole first introduction")
            await member.edit(nick=applied, reason="GuildConsole first introduction")
        except discord.HTTPException:
            if added:
                try:
                    await member.remove_roles(*added, reason="Introduction could not complete")
                except discord.HTTPException:
                    logger.exception("Could not roll back introduction roles guild=%s user=%s", guild_id, member.id)
            raise
        await self.post("/complete", {
            "guild_id": guild_id, "discord_user_id": member.id,
            "language_code": language, "server_number": server_number,
            "alliance": alliance.strip(), "nickname": nickname.strip(),
            "applied_nickname": applied,
        })
        return applied


class IntroStartView(discord.ui.View):
    def __init__(self, plugin: FirstIntroduction) -> None:
        super().__init__(timeout=None)
        self.plugin = plugin

    @discord.ui.button(label="Confirm and introduce yourself", style=discord.ButtonStyle.success,
                       custom_id="guildconsole:first-introduction:start")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.message is None or interaction.message.author != self.plugin.bot.user:
            await interaction.response.send_message("Invalid introduction prompt.", ephemeral=True)
            return
        footer = interaction.message.embeds[0].footer.text if interaction.message.embeds else ""
        if not footer or not footer.startswith("guild:") or not footer[6:].isdigit():
            await interaction.response.send_message("Invalid introduction prompt.", ephemeral=True)
            return
        try:
            await self.plugin.begin(interaction, int(footer[6:]))
        except Exception:
            logger.exception("Could not open introduction guild=%s", footer[6:])
            if not interaction.response.is_done():
                await interaction.response.send_message("Could not load the introduction. Try again later.", ephemeral=True)


class IntroLanguageSelect(discord.ui.Select):
    def __init__(self, languages: list[dict]) -> None:
        super().__init__(placeholder="Choose your language", min_values=1, max_values=1,
                         options=[discord.SelectOption(label=item["name"][:100], value=item["code"])
                                  for item in languages[:25]])

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.language = self.values[0]
        await interaction.response.edit_message(view=self.view)


class IntroServerSelect(discord.ui.Select):
    def __init__(self, numbers: list[str]) -> None:
        super().__init__(placeholder="Choose your server number", min_values=1, max_values=1,
                         options=[discord.SelectOption(label=value[:100], value=value)
                                  for value in numbers[:25]])

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.server_number = self.values[0]
        await interaction.response.edit_message(view=self.view)


class IntroSelectionsView(discord.ui.View):
    def __init__(self, plugin: FirstIntroduction, guild_id: int, user_id: int, config: dict) -> None:
        super().__init__(timeout=900)
        self.plugin = plugin
        self.guild_id = guild_id
        self.user_id = user_id
        self.language: str | None = None
        self.server_number: str | None = None
        self.add_item(IntroLanguageSelect(config["languages"]))
        self.add_item(IntroServerSelect(config["server_numbers"]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This form belongs to another member.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.primary)
    async def continue_form(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.language or not self.server_number:
            await interaction.response.send_message("Select both language and server number.", ephemeral=True)
            return
        await interaction.response.send_modal(IntroDetailsModal(
            self.plugin, self.guild_id, self.language, self.server_number
        ))


class IntroDetailsModal(discord.ui.Modal, title="First introduction"):
    alliance = discord.ui.TextInput(label="Alliance name", min_length=1, max_length=32)
    nickname = discord.ui.TextInput(label="Your nickname", min_length=1, max_length=64)

    def __init__(self, plugin: FirstIntroduction, guild_id: int, language: str, server_number: str) -> None:
        super().__init__()
        self.plugin = plugin
        self.guild_id = guild_id
        self.language = language
        self.server_number = server_number

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=interaction.guild is not None)
        try:
            applied = await self.plugin.finish(
                interaction, self.guild_id, self.language, self.server_number,
                str(self.alliance.value), str(self.nickname.value),
            )
            await interaction.followup.send(f"Introduction complete. Your nickname is **{applied}**.",
                                            ephemeral=interaction.guild is not None)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=interaction.guild is not None)
        except Exception:
            logger.exception("Introduction failed guild=%s user=%s", self.guild_id, interaction.user.id)
            await interaction.followup.send("Could not finish the introduction. Please try again.",
                                            ephemeral=interaction.guild is not None)
