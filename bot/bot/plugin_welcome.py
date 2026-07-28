from __future__ import annotations

import logging
from typing import Any

import discord
import httpx

from bot.config import settings

logger = logging.getLogger(__name__)

class WelcomeWorker:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self.base = settings.backend_url.rstrip("/")
        self.headers = {
            "X-ShieldNet-Service-Token": settings.internal_service_token,
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base}/api/v1/internal/plugin-welcome{path}",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def member_join(self, member: discord.Member) -> None:
        await self._post("/member-join", {
            "guild_id": member.guild.id,
            "user_id": member.id,
            "username": member.name,
            "display_name": member.display_name,
            "guild_name": member.guild.name,
            "bot": member.bot,
        })

    async def member_roles(self, member: discord.Member) -> None:
        result = await self._post("/member-roles", {
            "guild_id": member.guild.id,
            "user_id": member.id,
            "role_ids": [role.id for role in member.roles],
        })
        if result.get("delete_messages"):
            for task_id in result.get("task_ids") or []:
                await self.delete_task_messages(task_id)

    async def member_left(self, member: discord.Member) -> None:
        result = await self._post("/member-left", {
            "guild_id": member.guild.id,
            "user_id": member.id,
        })
        for task_id in result.get("task_ids") or []:
            await self.delete_task_messages(task_id)

    async def run_once(self) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base}/api/v1/internal/plugin-welcome/due",
                headers=self.headers,
            )
            response.raise_for_status()
            item = response.json().get("item")
        if not item:
            return

        task_id = str(item["id"])
        try:
            guild = self.bot.get_guild(int(item["guild_id"]))
            if guild is None:
                raise RuntimeError("Guild is unavailable")
            member = guild.get_member(int(item["user_id"]))
            if member is None:
                raise RuntimeError("Member is unavailable")

            required_role_id = int(item["required_role_id"])
            if any(role.id == required_role_id for role in member.roles):
                await self.member_roles(member)
                return

            channel = guild.get_channel(int(item["welcome_channel_id"]))
            if not isinstance(channel, discord.TextChannel):
                raise RuntimeError("Welcome channel is unavailable")

            content = str(item["message_template"])
            content = content.replace("{mention}", member.mention)
            content = content.replace("{username}", member.name)
            content = content.replace("{display_name}", member.display_name)
            content = content.replace("{guild}", guild.name)
            content = content.replace(
                "{verification_channel}",
                f"<#{int(item['verification_channel_id'])}>",
            )

            message = await channel.send(
                content,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            await self._post("/message-result", {
                "task_id": task_id,
                "message_id": message.id,
                "error": None,
            })
        except Exception as exc:
            logger.exception("Welcome delivery failed task=%s", task_id)
            await self._post("/message-result", {
                "task_id": task_id,
                "message_id": None,
                "error": str(exc)[:2000],
            })

    async def delete_task_messages(self, task_id: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base}/api/v1/internal/plugin-welcome/tasks/{task_id}/messages",
                headers=self.headers,
            )
            response.raise_for_status()
            payload = response.json()
        guild = self.bot.get_guild(int(payload.get("guild_id") or 0))
        if guild:
            for message_id in payload.get("message_ids") or []:
                for channel in guild.text_channels:
                    try:
                        message = await channel.fetch_message(int(message_id))
                        await message.delete()
                        break
                    except discord.NotFound:
                        continue
                    except discord.Forbidden:
                        break
                    except discord.HTTPException:
                        continue
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.delete(
                f"{self.base}/api/v1/internal/plugin-welcome/tasks/{task_id}/messages",
                headers=self.headers,
            )
            response.raise_for_status()
