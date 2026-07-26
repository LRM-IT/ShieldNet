from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.plugins.base import BackendPlugin


router = APIRouter(prefix="/guilds/{guild_id}")


@router.get("/health")
async def health(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await require_guild_management(session, current_user, guild_id)
    return {
        "plugin": "guild-dm-broadcast",
        "version": "1.0.0",
        "guild_id": str(guild_id),
        "status": "ready",
        "delivery_runtime": "planned",
    }


@router.get("/settings")
async def settings(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await require_guild_management(session, current_user, guild_id)
    row = (
        await session.execute(
            text("""
                SELECT guild_id, enabled, max_recipients, cooldown_minutes,
                       batch_size, delay_between_batches_seconds, default_locale
                FROM plugin_guild_dm_broadcast.settings
                WHERE guild_id=:guild_id
            """),
            {"guild_id": guild_id},
        )
    ).mappings().first()
    if row is None:
        return {
            "guild_id": str(guild_id),
            "enabled": True,
            "max_recipients": 1000,
            "cooldown_minutes": 30,
            "batch_size": 10,
            "delay_between_batches_seconds": 5,
            "default_locale": "en",
        }
    result = dict(row)
    result["guild_id"] = str(result["guild_id"])
    return result


class GuildDMBroadcastPlugin(BackendPlugin):
    def router(self) -> APIRouter:
        return router
