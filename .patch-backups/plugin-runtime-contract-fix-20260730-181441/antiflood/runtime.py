from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)
_started = False


async def setup(context: Any) -> None:
    logger.info(
        "AntiFlood plugin setup guild_id=%s plugin_key=%s generation=%s",
        getattr(context, "guild_id", None),
        getattr(context, "plugin_key", None),
        getattr(context, "generation", None),
    )


async def start(context: Any) -> None:
    global _started
    _started = True
    logger.info(
        "AntiFlood plugin started guild_id=%s plugin_key=%s",
        getattr(context, "guild_id", None),
        getattr(context, "plugin_key", None),
    )


async def stop(context: Any) -> None:
    global _started
    _started = False
    logger.info(
        "AntiFlood plugin stopped guild_id=%s plugin_key=%s",
        getattr(context, "guild_id", None),
        getattr(context, "plugin_key", None),
    )


async def health(context: Any) -> dict[str, Any]:
    return {
        "status": "ready" if _started else "stopped",
        "plugin_key": "antiflood",
        "version": "1.0.2",
        "guild_id": getattr(context, "guild_id", None),
    }
