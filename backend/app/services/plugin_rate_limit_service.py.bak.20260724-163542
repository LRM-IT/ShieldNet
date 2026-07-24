from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: float
    reset_after: float


class PluginRateLimitService:
    """
    Sliding-window limiter local to one Backend process.

    Key format:
        guild_id:plugin_key:scope
    """

    def __init__(self) -> None:
        self.window_seconds = float(
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

        if self.window_seconds <= 0:
            raise RuntimeError(
                "PLUGIN_RATE_LIMIT_WINDOW_SECONDS must be positive"
            )

        self._requests: dict[
            str,
            Deque[float],
        ] = defaultdict(deque)

        self._lock = asyncio.Lock()
        self._last_cleanup = 0.0

    def limit_for_scope(self, scope: str) -> int:
        limits = {
            "runtime.context": self.context_limit,
            "runtime.token.refresh": self.refresh_limit,
            "runtime.read": self.runtime_read_limit,
            "discord.send.message": self.send_message_limit,
        }

        return limits.get(
            scope,
            self.default_limit,
        )

    async def check(
        self,
        *,
        guild_id: int,
        plugin_key: str,
        scope: str,
    ) -> RateLimitResult:
        now = time.monotonic()
        limit = self.limit_for_scope(scope)

        if limit <= 0:
            return RateLimitResult(
                allowed=False,
                limit=0,
                remaining=0,
                retry_after=self.window_seconds,
                reset_after=self.window_seconds,
            )

        key = (
            f"{guild_id}:"
            f"{plugin_key}:"
            f"{scope}"
        )

        cutoff = now - self.window_seconds

        async with self._lock:
            bucket = self._requests[key]

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                oldest = bucket[0]

                retry_after = max(
                    0.001,
                    self.window_seconds - (now - oldest),
                )

                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    retry_after=retry_after,
                    reset_after=retry_after,
                )

            bucket.append(now)

            remaining = max(
                0,
                limit - len(bucket),
            )

            reset_after = (
                self.window_seconds
                if not bucket
                else max(
                    0.001,
                    self.window_seconds
                    - (now - bucket[0]),
                )
            )

            if (
                now - self._last_cleanup
                >= self.window_seconds
            ):
                self._cleanup_locked(cutoff)
                self._last_cleanup = now

            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=remaining,
                retry_after=0.0,
                reset_after=reset_after,
            )

    def _cleanup_locked(
        self,
        cutoff: float,
    ) -> None:
        empty_keys: list[str] = []

        for key, bucket in self._requests.items():
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if not bucket:
                empty_keys.append(key)

        for key in empty_keys:
            self._requests.pop(key, None)


plugin_rate_limiter = PluginRateLimitService()
