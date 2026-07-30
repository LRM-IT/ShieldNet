from __future__ import annotations

import asyncio
import logging

import discord
import httpx

from bot.config import settings

logger = logging.getLogger(__name__)


class AntiFloodWorker:
    def __init__(self, client: discord.Client) -> None:
        self.client = client
        self.base_url = settings.backend_url.rstrip("/")
        self.headers = {
            "X-ShieldNet-Service-Token": settings.internal_service_token,
            "Content-Type": "application/json",
        }

    async def process(self, message: discord.Message) -> None:
        if message.guild is None:
            return

        member = message.author
        if not isinstance(member, discord.Member):
            cached = message.guild.get_member(message.author.id)
            if cached is None:
                try:
                    cached = await message.guild.fetch_member(message.author.id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    logger.warning(
                        "AntiFlood skipped: member_unavailable guild=%s channel=%s user=%s",
                        message.guild.id,
                        message.channel.id,
                        message.author.id,
                    )
                    return
            member = cached

        permissions = member.guild_permissions
        payload = {
            "guild_id": message.guild.id,
            "channel_id": message.channel.id,
            "user_id": member.id,
            "bot": member.bot,
            "administrator": permissions.administrator,
            "manage_messages": permissions.manage_messages,
            "role_ids": [role.id for role in member.roles],
        }

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/internal/plugin-antiflood/check",
                    headers=self.headers,
                    json=payload,
                )
            response.raise_for_status()
            result = response.json()
        except Exception:
            logger.exception(
                "AntiFlood check failed guild=%s channel=%s user=%s",
                message.guild.id,
                message.channel.id,
                member.id,
            )
            return

        logger.warning(
            "AntiFlood decision guild=%s channel=%s user=%s message=%s result=%s",
            message.guild.id,
            message.channel.id,
            member.id,
            message.id,
            result,
        )

        if result.get("action") != "delete":
            return

        bot_member = message.guild.me
        channel_permissions = (
            message.channel.permissions_for(bot_member)
            if bot_member is not None and hasattr(message.channel, "permissions_for")
            else None
        )

        if channel_permissions is not None and not channel_permissions.manage_messages:
            logger.error(
                "AntiFlood cannot delete: missing Manage Messages guild=%s channel=%s bot=%s",
                message.guild.id,
                message.channel.id,
                bot_member.id if bot_member else None,
            )
            return

        try:
            await message.delete()
            logger.warning(
                "AntiFlood deleted message guild=%s channel=%s user=%s message=%s",
                message.guild.id,
                message.channel.id,
                member.id,
                message.id,
            )
        except discord.Forbidden:
            logger.exception(
                "AntiFlood delete forbidden guild=%s channel=%s message=%s",
                message.guild.id,
                message.channel.id,
                message.id,
            )
            return
        except discord.NotFound:
            logger.warning(
                "AntiFlood message already absent guild=%s channel=%s message=%s",
                message.guild.id,
                message.channel.id,
                message.id,
            )
            return
        except discord.HTTPException:
            logger.exception(
                "AntiFlood delete HTTP failure guild=%s channel=%s message=%s",
                message.guild.id,
                message.channel.id,
                message.id,
            )
            return

        remaining = max(1, int(result.get("remaining") or 1))
        try:
            warning = await message.channel.send(
                f"{member.mention}, повторное сообщение в этом канале "
                f"можно отправить через {remaining} сек.",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            asyncio.create_task(self._delete_warning(warning))
        except (discord.Forbidden, discord.HTTPException):
            logger.exception(
                "AntiFlood warning failed guild=%s channel=%s user=%s",
                message.guild.id,
                message.channel.id,
                member.id,
            )

    @staticmethod
    async def _delete_warning(message: discord.Message) -> None:
        await asyncio.sleep(5)
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass
