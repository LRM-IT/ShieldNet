from __future__ import annotations

from datetime import UTC, datetime, timedelta

import discord
import httpx

from bot.config import settings


class ChannelCleanup:
    def __init__(self, bot):
        self.bot = bot
        self.base = settings.backend_url.rstrip("/") + "/api/v1/internal/plugin-channel-cleanup"
        self.headers = {"X-ShieldNet-Service-Token": settings.internal_service_token}

    async def request(self, method: str, path: str, **kwargs):
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.request(method, f"{self.base}{path}", headers=self.headers, **kwargs)
            response.raise_for_status()
            return response.json()

    async def run_due(self, guild: discord.Guild) -> None:
        claim = await self.request("POST", f"/guilds/{guild.id}/claim")
        if not claim.get("claimed"):
            return
        deleted = 0
        scanned = 0
        errors: list[str] = []
        for target in claim.get("targets") or []:
            try:
                result = await self._clean_target(guild, target)
                deleted += result[0]
                scanned += result[1]
            except Exception as exc:
                errors.append(f"{target.get('channel_id')}: {str(exc)[:240]}")
        await self.request(
            "POST",
            f"/guilds/{guild.id}/result",
            json={
                "run_id": claim["run_id"],
                "deleted_messages": deleted,
                "scanned_channels": scanned,
                "errors": errors[:100],
            },
        )

    async def _clean_target(self, guild: discord.Guild, target: dict) -> tuple[int, int]:
        channel_id = int(target["channel_id"])
        channel = guild.get_channel_or_thread(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden):
                raise RuntimeError("Channel or thread was not found or is inaccessible")
        cutoff = datetime.now(UTC) - timedelta(days=int(target.get("retention_days") or 30))
        keep_pinned = bool(target.get("keep_pinned", True))
        if isinstance(channel, discord.ForumChannel):
            threads: dict[int, discord.Thread] = {thread.id: thread for thread in channel.threads}
            async for thread in channel.archived_threads(limit=None):
                threads[thread.id] = thread
            deleted = 0
            scanned = 0
            for thread in threads.values():
                count = await self._purge(thread, cutoff, keep_pinned)
                deleted += count
                scanned += 1
            return deleted, scanned
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            return await self._purge(channel, cutoff, keep_pinned), 1
        raise RuntimeError("Only text channels, forum channels and threads are supported")

    @staticmethod
    async def _purge(channel: discord.TextChannel | discord.Thread, cutoff: datetime, keep_pinned: bool) -> int:
        deleted = await channel.purge(
            limit=None,
            before=cutoff,
            check=lambda message: not (keep_pinned and message.pinned),
            bulk=True,
            reason="GuildConsole Channel Cleanup retention policy",
        )
        return len(deleted)
