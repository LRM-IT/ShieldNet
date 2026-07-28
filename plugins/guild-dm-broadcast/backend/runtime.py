from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("shieldnet.plugin.guild_dm_broadcast")


async def setup(context: Any) -> None:
    logger.info(
        "Guild DM Broadcast setup guild_id=%s generation=%s",
        context.guild_id,
        context.generation,
    )


async def start(context: Any) -> None:
    logger.info(
        "Guild DM Broadcast started guild_id=%s",
        context.guild_id,
    )


async def stop(context: Any) -> None:
    logger.info(
        "Guild DM Broadcast stopped guild_id=%s",
        context.guild_id,
    )
