from __future__ import annotations

import logging
import time
from urllib.parse import quote

import discord
import httpx

from bot.backend import BackendClient
from bot.config import settings

logger = logging.getLogger(__name__)


class TranslatorGroups:
    def __init__(self, bot: discord.Client, backend: BackendClient) -> None:
        self.bot = bot
        self.backend = backend
        self.base = settings.backend_url.rstrip("/") + "/api/v1/internal/plugin-translator-groups"
        self.headers = {"X-ShieldNet-Service-Token": settings.internal_service_token}
        self.cache: dict[int, tuple[float, dict]] = {}

    async def configuration(self, guild_id: int, *, refresh: bool = False) -> dict:
        cached = self.cache.get(guild_id)
        if cached and cached[0] > time.monotonic() and not refresh:
            return cached[1]
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base}/guilds/{guild_id}/configuration", headers=self.headers)
            response.raise_for_status()
            config = response.json()
        self.cache[guild_id] = (time.monotonic() + 30, config)
        return config

    async def command(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(self.base + path, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()
        self.cache.pop(int(payload["guild_id"]), None)
        return result

    async def unbind(self, guild_id: int, group: str, channel_id: int) -> None:
        path = f"/guilds/{guild_id}/groups/{quote(group, safe='')}/channels/{channel_id}"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.delete(self.base + path, headers=self.headers)
            response.raise_for_status()
        self.cache.pop(guild_id, None)

    @staticmethod
    def targets(config: dict, source_id: int) -> list[tuple[int, str]]:
        result: dict[int, str] = {}
        for group in config.get("groups", []):
            if not group.get("enabled"):
                continue
            channels = group.get("channels", [])
            source = next((item for item in channels if item["channel_id"] == str(source_id)), None)
            if source is None:
                continue
            for item in channels:
                target_id = int(item["channel_id"])
                if target_id != source_id and item["language"] != source["language"]:
                    result.setdefault(target_id, item["language"])
        return list(result.items())

    async def process(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot or message.webhook_id or not message.content.strip():
            return
        config = await self.configuration(message.guild.id)
        if not config["enabled"]:
            return
        for channel_id, language in self.targets(config, message.channel.id):
            channel = message.guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue
            try:
                response = await self.backend.execute_ai(
                    guild_id=message.guild.id,
                    module_key="translator",
                    capability="translation",
                    input_text=message.content,
                    source_language="auto",
                    target_language=language,
                    metadata={
                        "origin": "translator_groups",
                        "source_message_id": str(message.id),
                        "source_channel_id": str(message.channel.id),
                        "target_channel_id": str(channel_id),
                    },
                )
                translated = str(response.get("text") or "").strip()
                if not translated:
                    continue
                suffix = f"\n\n↗ {message.jump_url}" if config.get("include_source_link", True) else ""
                chunks = self._chunks(translated, 1900 - len(suffix))
                webhook = await self._webhook(channel)
                for index, chunk in enumerate(chunks):
                    await webhook.send(
                        content=chunk + (suffix if index == len(chunks) - 1 else ""),
                        username=message.author.display_name[:80],
                        avatar_url=message.author.display_avatar.url,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
            except Exception:
                logger.exception("Group translation failed guild=%s source=%s target=%s",
                                 message.guild.id, message.id, channel_id)

    async def _webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        hooks = await channel.webhooks()
        for hook in hooks:
            if hook.name == "GuildConsole Translator" and hook.user == self.bot.user:
                return hook
        return await channel.create_webhook(name="GuildConsole Translator")

    @staticmethod
    def _chunks(value: str, size: int) -> list[str]:
        return [value[index:index + size] for index in range(0, len(value), size)]
