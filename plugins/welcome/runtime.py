from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from app.plugins.base import BackendPlugin

logger = logging.getLogger(__name__)
_process_started = False


class WelcomePlugin(BackendPlugin):
    """In-process backend wrapper for Welcome."""

    def router(self) -> APIRouter | None:
        # HTTP routes are registered by ShieldNet core.
        return None

    async def startup(self) -> None:
        logger.info(
            "Welcome backend plugin started plugin_key=%s",
            self.key,
        )

    async def shutdown(self) -> None:
        logger.info(
            "Welcome backend plugin stopped plugin_key=%s",
            self.key,
        )


async def setup(context: Any) -> None:
    """Out-of-process runtime setup callback."""
    logger.info(
        "Welcome runtime setup guild_id=%s plugin_key=%s generation=%s",
        getattr(context, "guild_id", None),
        getattr(context, "plugin_key", None),
        getattr(context, "generation", None),
    )


async def start(context: Any) -> None:
    """Out-of-process runtime start callback."""
    global _process_started
    _process_started = True
    logger.info(
        "Welcome runtime started guild_id=%s plugin_key=%s",
        getattr(context, "guild_id", None),
        getattr(context, "plugin_key", None),
    )


async def stop(context: Any) -> None:
    """Out-of-process runtime stop callback."""
    global _process_started
    _process_started = False
    logger.info(
        "Welcome runtime stopped guild_id=%s plugin_key=%s",
        getattr(context, "guild_id", None),
        getattr(context, "plugin_key", None),
    )


async def health(context: Any) -> dict[str, Any]:
    return {
        "status": "ready" if _process_started else "stopped",
        "plugin_key": "welcome",
        "guild_id": getattr(context, "guild_id", None),
    }
