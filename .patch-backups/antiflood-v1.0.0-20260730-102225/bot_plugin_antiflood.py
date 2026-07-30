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
        if message.guild is None or not isinstance(message.author, discord.Member):
            return

        permissions = message.author.guild_permissions
        payload = {
            "guild_id": message.guild.id,
            "channel_id": message.channel.id,
            "user_id": message.author.id,
            "bot": message.author.bot,
            "administrator": permissions.administrator,
            "manage_messages": permissions.manage_messages,
            "role_ids": [role.id for role in message.author.roles],
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
                message.author.id,
            )
            return

        if result.get("action") != "delete":
            return

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            logger.warning(
                "AntiFlood could not delete message guild=%s channel=%s message=%s",
                message.guild.id,
                message.channel.id,
                message.id,
            )
            return

        remaining = max(1, int(result.get("remaining") or 1))
        try:
            warning = await message.channel.send(
                f"{message.author.mention}, повторное сообщение в этом канале "
                f"можно отправить через {remaining} сек.",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            asyncio.create_task(self._delete_warning(warning))
        except (discord.Forbidden, discord.HTTPException):
            logger.warning(
                "AntiFlood warning failed guild=%s channel=%s user=%s",
                message.guild.id,
                message.channel.id,
                message.author.id,
            )

    @staticmethod
    async def _delete_warning(message: discord.Message) -> None:
        await asyncio.sleep(5)
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass
