from __future__ import annotations

import logging
import time
import hashlib
import re
from io import BytesIO
from urllib.parse import quote

import discord
import httpx
from redis.asyncio import Redis

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
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)

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
        if message.guild is None or message.author.bot or message.webhook_id:
            return
        if not message.content.strip() and not message.attachments and not message.stickers:
            return
        config = await self.configuration(message.guild.id)
        if not config["enabled"]:
            return
        attachments = await self._attachments(message) if config.get("forward_attachments", True) else []
        for channel_id, language in self.targets(config, message.channel.id):
            channel = message.guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue
            try:
                translated = ""
                if message.content.strip():
                    try:
                        source_text = message.content[:int(config.get("max_source_characters", 4000))]
                        protected_text, protected = self._protect_terms(source_text, config.get("protected_terms", []))
                        translated = await self._cached_translation(message, channel_id, language, protected_text, config)
                        translated = self._restore_terms(translated, protected)
                        if not translated:
                            translated = source_text if config.get("fallback_to_original", True) else ""
                    except Exception:
                        logger.exception("Text translation failed; forwarding original guild=%s source=%s target=%s",
                                         message.guild.id, message.id, channel_id)
                        translated = message.content[:int(config.get("max_source_characters", 4000))] if config.get("fallback_to_original", True) else ""
                fallback_links = [url for item in attachments if (url := item.get("fallback_url"))]
                if config.get("forward_stickers", True):
                    fallback_links.extend(sticker.url for sticker in message.stickers)
                suffix_parts = [f"📎 {url}" for url in fallback_links]
                if config.get("include_source_link", True):
                    suffix_parts.append(f"↗ {message.jump_url}")
                suffix_body = "\n".join(suffix_parts)
                if len(suffix_body) > 1700:
                    suffix_body = suffix_body[:1697] + "..."
                suffix = ("\n\n" + suffix_body) if suffix_body else ""
                chunks = self._chunks(translated, 1900 - len(suffix)) if translated else [""]
                webhook = await self._webhook(channel)
                for index, chunk in enumerate(chunks):
                    files = self._files(attachments, message.guild.filesize_limit) if index == 0 else []
                    await webhook.send(
                        content=(chunk + (suffix if index == len(chunks) - 1 else "")) or None,
                        files=files,
                        username=message.author.display_name[:80],
                        avatar_url=message.author.display_avatar.url,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
            except Exception:
                logger.exception("Group translation failed guild=%s source=%s target=%s",
                                 message.guild.id, message.id, channel_id)

    async def _cached_translation(self, message: discord.Message, channel_id: int, language: str, source_text: str, config: dict) -> str:
        use_cache = bool(config.get("cache_enabled", True)) and len(source_text.strip()) >= int(config.get("cache_min_characters", 4))
        terms_version = "\0".join(str(x).casefold() for x in config.get("protected_terms", []))
        terms_hash = hashlib.sha256(terms_version.encode("utf-8")).hexdigest() if terms_version else ""
        digest = hashlib.sha256(f"{language}\0{terms_version}\0{source_text.strip()}".encode("utf-8")).hexdigest()
        key = f"shieldnet:translator-cache:{message.guild.id}:{digest}"
        if use_cache:
            cached = await self.redis.get(key)
            if cached is not None:
                await self.redis.incr(f"shieldnet:translator-cache-hits:{message.guild.id}")
                return cached
            await self.redis.incr(f"shieldnet:translator-cache-misses:{message.guild.id}")
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    archive = await client.post(f"{self.base}/archive/lookup", headers=self.headers, json={"source_text":source_text,"target_language":language,"protected_terms_hash":terms_hash})
                    archive.raise_for_status()
                    archived = archive.json()
                if archived.get("found"):
                    translated = str(archived.get("translated_text") or "")
                    if translated:
                        await self._store_local_cache(message.guild.id, key, translated, config)
                        return translated
            except Exception:
                logger.warning("Shared translation archive lookup failed guild=%s", message.guild.id, exc_info=True)
        response = await self.backend.execute_ai(
            guild_id=message.guild.id,module_key="translator",capability="translation",input_text=source_text,
            source_language="auto",target_language=language,
            metadata={"origin":"translator_groups","source_message_id":str(message.id),"source_channel_id":str(message.channel.id),"target_channel_id":str(channel_id)},
        )
        translated = str(response.get("text") or "").strip()
        if use_cache and translated:
            await self._store_local_cache(message.guild.id, key, translated, config)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    stored = await client.post(f"{self.base}/archive/store", headers=self.headers, json={"source_text":source_text,"target_language":language,"protected_terms_hash":terms_hash,"translated_text":translated})
                    stored.raise_for_status()
            except Exception:
                logger.warning("Shared translation archive store failed guild=%s", message.guild.id, exc_info=True)
        return translated

    async def _store_local_cache(self, guild_id: int, key: str, translated: str, config: dict) -> None:
        ttl = int(config.get("cache_ttl_hours", 72)) * 3600
        index = f"shieldnet:translator-cache-index:{guild_id}"
        pipe = self.redis.pipeline()
        pipe.set(key, translated, ex=ttl)
        pipe.zadd(index, {key: time.time()})
        pipe.expire(index, ttl)
        await pipe.execute()
        excess = int(await self.redis.zcard(index)) - int(config.get("cache_max_entries", 2000))
        if excess > 0:
            expired = await self.redis.zpopmin(index, excess)
            if expired:
                await self.redis.delete(*(item[0] for item in expired))

    @staticmethod
    def _protect_terms(value: str, terms: list[str]) -> tuple[str, dict[str, str]]:
        cleaned = sorted({str(term).strip() for term in terms if str(term).strip()}, key=len, reverse=True)
        if not cleaned:
            return value, {}
        pattern = re.compile("|".join(re.escape(term) for term in cleaned), re.IGNORECASE)
        replacements: dict[str, str] = {}
        def replace(match: re.Match[str]) -> str:
            token = f"__SNPROTECTED{len(replacements)}__"
            replacements[token] = match.group(0)
            return token
        return pattern.sub(replace, value), replacements

    @staticmethod
    def _restore_terms(value: str, replacements: dict[str, str]) -> str:
        for token, original in replacements.items():
            value = re.sub(re.escape(token), lambda _match, text=original: text, value, flags=re.IGNORECASE)
        return value

    async def _webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        hooks = await channel.webhooks()
        for hook in hooks:
            if hook.name == "GuildConsole Translator" and hook.user == self.bot.user:
                return hook
        return await channel.create_webhook(name="GuildConsole Translator")

    @staticmethod
    async def _attachments(message: discord.Message) -> list[dict]:
        result = []
        for attachment in message.attachments[:10]:
            if attachment.size > message.guild.filesize_limit:
                result.append({"fallback_url": attachment.url, "size": attachment.size})
                continue
            try:
                data = await attachment.read(use_cached=True)
                result.append({
                    "data": data,
                    "filename": attachment.filename,
                    "description": attachment.description,
                    "spoiler": attachment.is_spoiler(),
                    "size": attachment.size,
                    "fallback_url": None,
                })
            except (discord.HTTPException, OSError):
                logger.warning("Could not download attachment message=%s attachment=%s", message.id, attachment.id)
                result.append({"fallback_url": attachment.url, "size": attachment.size})
        for attachment in message.attachments[10:]:
            result.append({"fallback_url": attachment.url, "size": attachment.size})
        return result

    @staticmethod
    def _files(attachments: list[dict], upload_limit: int) -> list[discord.File]:
        files = []
        for item in attachments:
            if not item.get("data") or item["size"] > upload_limit:
                continue
            files.append(discord.File(
                BytesIO(item["data"]), filename=item["filename"],
                spoiler=item["spoiler"], description=item.get("description"),
            ))
        return files

    @staticmethod
    def _chunks(value: str, size: int) -> list[str]:
        return [value[index:index + size] for index in range(0, len(value), size)]
