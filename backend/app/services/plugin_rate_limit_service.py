from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.db.session import AsyncSessionFactory


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: float
    reset_after: float


class PluginRateLimitService:
    """
    PostgreSQL-backed fixed-window rate limiter.

    The counter is shared by every Backend worker and node
    connected to the same ShieldNet database.
    """

    def __init__(self) -> None:
        self.window_seconds = int(
            os.getenv(
                "PLUGIN_RATE_LIMIT_WINDOW_SECONDS",
                "60",
            )
        )

        self.default_limit = int(
            os.getenv(
                "PLUGIN_RATE_LIMIT_DEFAULT",
                "60",
            )
        )

        self.context_limit = int(
            os.getenv(
                "PLUGIN_RATE_LIMIT_CONTEXT",
                "120",
            )
        )

        self.refresh_limit = int(
            os.getenv(
                "PLUGIN_RATE_LIMIT_TOKEN_REFRESH",
                "12",
            )
        )

        self.runtime_read_limit = int(
            os.getenv(
                "PLUGIN_RATE_LIMIT_RUNTIME_READ",
                "60",
            )
        )

        self.send_message_limit = int(
            os.getenv(
                "PLUGIN_RATE_LIMIT_SEND_MESSAGE",
                "30",
            )
        )

        self.cleanup_interval_seconds = int(
            os.getenv(
                "PLUGIN_RATE_LIMIT_CLEANUP_SECONDS",
                "300",
            )
        )

        self.retention_seconds = int(
            os.getenv(
                "PLUGIN_RATE_LIMIT_RETENTION_SECONDS",
                "3600",
            )
        )

        if self.window_seconds < 1:
            raise RuntimeError(
                "PLUGIN_RATE_LIMIT_WINDOW_SECONDS "
                "must be at least 1"
            )

        self._last_cleanup_monotonic = 0.0

    def limit_for_scope(self, scope: str) -> int:
        return {
            "runtime.context": self.context_limit,
            "runtime.token.refresh": self.refresh_limit,
            "runtime.read": self.runtime_read_limit,
            "discord.send.message": self.send_message_limit,
        }.get(
            scope,
            self.default_limit,
        )

    def _window_start(
        self,
        now: datetime,
    ) -> datetime:
        timestamp = int(now.timestamp())

        window_timestamp = (
            timestamp
            - timestamp % self.window_seconds
        )

        return datetime.fromtimestamp(
            window_timestamp,
            tz=UTC,
        )

    async def check(
        self,
        *,
        guild_id: int,
        plugin_key: str,
        scope: str,
    ) -> RateLimitResult:
        limit = self.limit_for_scope(scope)
        now = datetime.now(UTC)
        window_start = self._window_start(now)
        window_end = window_start + timedelta(
            seconds=self.window_seconds
        )

        reset_after = max(
            0.001,
            (window_end - now).total_seconds(),
        )

        if limit <= 0:
            return RateLimitResult(
                allowed=False,
                limit=0,
                remaining=0,
                retry_after=reset_after,
                reset_after=reset_after,
            )

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text("""
                    INSERT INTO plugins.rate_limit_windows (
                        guild_id,
                        plugin_key,
                        scope,
                        window_started_at,
                        request_count,
                        updated_at
                    )
                    VALUES (
                        :guild_id,
                        :plugin_key,
                        :scope,
                        :window_started_at,
                        1,
                        NOW()
                    )
                    ON CONFLICT (
                        guild_id,
                        plugin_key,
                        scope,
                        window_started_at
                    )
                    DO UPDATE SET
                        request_count =
                            plugins.rate_limit_windows
                            .request_count + 1,
                        updated_at = NOW()
                    RETURNING request_count
                """),
                {
                    "guild_id": guild_id,
                    "plugin_key": plugin_key[:128],
                    "scope": scope[:128],
                    "window_started_at": window_start,
                },
            )

            request_count = int(
                result.scalar_one()
            )

            await session.commit()

        await self._cleanup_if_due()

        allowed = request_count <= limit
        remaining = max(
            0,
            limit - request_count,
        )

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            remaining=remaining,
            retry_after=(
                0.0
                if allowed
                else reset_after
            ),
            reset_after=reset_after,
        )

    async def _cleanup_if_due(self) -> None:
        now_monotonic = time.monotonic()

        if (
            now_monotonic
            - self._last_cleanup_monotonic
            < self.cleanup_interval_seconds
        ):
            return

        self._last_cleanup_monotonic = (
            now_monotonic
        )

        cutoff = datetime.now(UTC) - timedelta(
            seconds=self.retention_seconds
        )

        try:
            async with AsyncSessionFactory() as session:
                await session.execute(
                    text("""
                        DELETE FROM
                            plugins.rate_limit_windows
                        WHERE updated_at < :cutoff
                    """),
                    {"cutoff": cutoff},
                )

                await session.commit()
        except Exception:
            # Cleanup must not break Plugin API requests.
            return


plugin_rate_limiter = PluginRateLimitService()
