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

    async def publish_panel(self, guild: discord.Guild) -> discord.Message:
        config = await self.configuration(guild.id)
        if not config["enabled"] or not config["channel_id"]:
            raise ValueError("Configure and enable Language Selection first")
        channel_id = int(config["channel_id"])
        channel = guild.get_channel_or_thread(channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)) or channel.guild.id != guild.id:
            raise ValueError("Configured channel or thread is unavailable")
        lines = [f'{item["flag"]} — {item["name"]}' for item in config["languages"]]
        if not lines or any(not item["flag"] for item in config["languages"]):
            raise ValueError("Every language needs a flag")
        message = await channel.send("Choose your language by reacting with one flag:\n" + "\n".join(lines))
        try:
            for item in config["languages"]:
                await message.add_reaction(item["flag"])
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(f"{self.base}/panel", headers=self.headers, json={
                    "guild_id": guild.id, "channel_id": str(channel_id), "message_id": str(message.id),
                })
                response.raise_for_status()
        except Exception:
            await message.delete()
            raise
        previous_id = config.get("message_id")
        if previous_id and str(message.id) != previous_id:
            try:
                previous = await channel.fetch_message(int(previous_id))
                await previous.delete()
            except discord.HTTPException:
                logger.warning("Could not remove prior language panel guild=%s message=%s", guild.id, previous_id)
        return message

    async def on_reaction(self, payload: discord.RawReactionActionEvent, added: bool) -> None:
        if payload.guild_id is None or self.bot.user is None or payload.user_id == self.bot.user.id:
            return
        config = await self.configuration(payload.guild_id)
        if not config["enabled"] or str(payload.message_id) != config.get("message_id"):
            return
        if str(payload.channel_id) != config.get("channel_id"):
            return
        emoji = str(payload.emoji)
        item = next((language for language in config["languages"] if language["flag"] == emoji), None)
        if item is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = payload.member or guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except discord.NotFound:
                return
        if member.bot:
            return
        roles_by_code = config["language_roles"]
        role_id = roles_by_code.get(item["code"])
        role = guild.get_role(int(role_id)) if role_id else None
        if role is None:
            logger.warning("Language role missing guild=%s code=%s", guild.id, item["code"])
            return
        bot_member = guild.me
        if bot_member is None or role >= bot_member.top_role:
            logger.warning("Language role above bot guild=%s role=%s", guild.id, role.id)
            return
        if added:
            old_roles = [current for current in member.roles
                         if current.id != role.id and str(current.id) in roles_by_code.values()]
            if any(old >= bot_member.top_role for old in old_roles):
                return
            if role not in member.roles:
                await member.add_roles(role, reason="GuildConsole flag language selection")
            if old_roles:
                await member.remove_roles(*old_roles, reason="GuildConsole language changed")
            channel = guild.get_channel_or_thread(payload.channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(payload.channel_id)
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                message = await channel.fetch_message(payload.message_id)
                for language in config["languages"]:
                    if language["flag"] != emoji:
                        try:
                            await message.remove_reaction(language["flag"], member)
                        except discord.HTTPException:
                            logger.warning("Could not clear old language reaction guild=%s user=%s", guild.id, member.id)
        elif role in member.roles:
            await member.remove_roles(role, reason="GuildConsole language flag removed")
