from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AntiFlood plugin"])
internal_router = APIRouter(
    prefix="/internal/plugin-antiflood",
    tags=["Internal AntiFlood plugin"],
    dependencies=[Depends(verify_internal_service_token)],
)


class AntiFloodRule(BaseModel):
    channel_id: int
    cooldown_seconds: int = Field(ge=1, le=604800)
    enabled: bool = True


class AntiFloodSettings(BaseModel):
    enabled: bool = True
    ignore_bots: bool = True
    ignore_administrators: bool = True
    ignore_moderators: bool = True
    rules: list[AntiFloodRule] = Field(default_factory=list)
    excluded_role_ids: list[int] = Field(default_factory=list)
    excluded_user_ids: list[int] = Field(default_factory=list)


class CheckMessage(BaseModel):
    guild_id: int
    channel_id: int
    user_id: int
    bot: bool = False
    administrator: bool = False
    manage_messages: bool = False
    role_ids: list[int] = Field(default_factory=list)


async def _auth(guild_id: int, user: User, session: AsyncSession) -> None:
    await require_guild_management(session, user, guild_id)


async def _read_settings(session: AsyncSession, guild_id: int) -> dict[str, Any]:
    settings = (
        await session.execute(
            text("""
                SELECT enabled,ignore_bots,ignore_administrators,ignore_moderators
                FROM plugin_antiflood.settings
                WHERE guild_id=:guild_id
            """),
            {"guild_id": guild_id},
        )
    ).mappings().first()

    rules = (
        await session.execute(
            text("""
                SELECT channel_id,cooldown_seconds,enabled
                FROM plugin_antiflood.rules
                WHERE guild_id=:guild_id
                ORDER BY id
            """),
            {"guild_id": guild_id},
        )
    ).mappings().all()

    roles = (
        await session.execute(
            text("""
                SELECT role_id FROM plugin_antiflood.role_exceptions
                WHERE guild_id=:guild_id ORDER BY role_id
            """),
            {"guild_id": guild_id},
        )
    ).scalars().all()

    users = (
        await session.execute(
            text("""
                SELECT user_id FROM plugin_antiflood.user_exceptions
                WHERE guild_id=:guild_id ORDER BY user_id
            """),
            {"guild_id": guild_id},
        )
    ).scalars().all()

    base = {
        "enabled": True,
        "ignore_bots": True,
        "ignore_administrators": True,
        "ignore_moderators": True,
    }
    if settings:
        base.update(dict(settings))
    base["rules"] = [dict(row) for row in rules]
    base["excluded_role_ids"] = list(roles)
    base["excluded_user_ids"] = list(users)
    return base


@router.get("/discord/guilds/{guild_id}/plugins/antiflood/settings")
async def get_settings(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _auth(guild_id, current_user, session)
    return await _read_settings(session, guild_id)


@router.put("/discord/guilds/{guild_id}/plugins/antiflood/settings")
async def save_settings(
    guild_id: int,
    payload: AntiFloodSettings,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _auth(guild_id, current_user, session)

    await session.execute(
        text("""
            INSERT INTO plugin_antiflood.settings(
                guild_id,enabled,ignore_bots,ignore_administrators,
                ignore_moderators,updated_at
            ) VALUES(
                :guild_id,:enabled,:ignore_bots,:ignore_administrators,
                :ignore_moderators,now()
            )
            ON CONFLICT(guild_id) DO UPDATE SET
                enabled=excluded.enabled,
                ignore_bots=excluded.ignore_bots,
                ignore_administrators=excluded.ignore_administrators,
                ignore_moderators=excluded.ignore_moderators,
                updated_at=now()
        """),
        {"guild_id": guild_id, **payload.model_dump(exclude={"rules", "excluded_role_ids", "excluded_user_ids"})},
    )

    await session.execute(
        text("DELETE FROM plugin_antiflood.rules WHERE guild_id=:guild_id"),
        {"guild_id": guild_id},
    )
    for rule in payload.rules:
        await session.execute(
            text("""
                INSERT INTO plugin_antiflood.rules(
                    guild_id,channel_id,cooldown_seconds,enabled,created_at,updated_at
                ) VALUES(:guild_id,:channel_id,:cooldown_seconds,:enabled,now(),now())
            """),
            {"guild_id": guild_id, **rule.model_dump()},
        )

    await session.execute(
        text("DELETE FROM plugin_antiflood.role_exceptions WHERE guild_id=:guild_id"),
        {"guild_id": guild_id},
    )
    for role_id in sorted(set(payload.excluded_role_ids)):
        await session.execute(
            text("""
                INSERT INTO plugin_antiflood.role_exceptions(guild_id,role_id)
                VALUES(:guild_id,:role_id)
            """),
            {"guild_id": guild_id, "role_id": role_id},
        )

    await session.execute(
        text("DELETE FROM plugin_antiflood.user_exceptions WHERE guild_id=:guild_id"),
        {"guild_id": guild_id},
    )
    for user_id in sorted(set(payload.excluded_user_ids)):
        await session.execute(
            text("""
                INSERT INTO plugin_antiflood.user_exceptions(guild_id,user_id)
                VALUES(:guild_id,:user_id)
            """),
            {"guild_id": guild_id, "user_id": user_id},
        )

    await session.commit()
    return await _read_settings(session, guild_id)


@internal_router.post("/check")
async def check_message(
    payload: CheckMessage,
    session: AsyncSession = Depends(get_db_session),
):
    settings = (
        await session.execute(
            text("""
                SELECT enabled,ignore_bots,ignore_administrators,ignore_moderators
                FROM plugin_antiflood.settings
                WHERE guild_id=:guild_id
            """),
            {"guild_id": payload.guild_id},
        )
    ).mappings().first()

    if settings is None:
        logger.info(
            "AntiFlood allow: settings_missing guild=%s channel=%s user=%s",
            payload.guild_id, payload.channel_id, payload.user_id,
        )
        return {"action": "allow", "reason": "settings_missing"}

    if not settings["enabled"]:
        logger.info(
            "AntiFlood allow: plugin_disabled guild=%s channel=%s user=%s",
            payload.guild_id, payload.channel_id, payload.user_id,
        )
        return {"action": "allow", "reason": "plugin_disabled"}

    rule = (
        await session.execute(
            text("""
                SELECT cooldown_seconds
                FROM plugin_antiflood.rules
                WHERE guild_id=:guild_id
                  AND channel_id=:channel_id
                  AND enabled=true
            """),
            {"guild_id": payload.guild_id, "channel_id": payload.channel_id},
        )
    ).mappings().first()

    if rule is None:
        logger.info(
            "AntiFlood allow: rule_missing guild=%s channel=%s user=%s",
            payload.guild_id, payload.channel_id, payload.user_id,
        )
        return {"action": "allow", "reason": "rule_missing"}

    if payload.bot and settings["ignore_bots"]:
        return {"action": "allow", "reason": "ignored_bot"}
    if payload.administrator and settings["ignore_administrators"]:
        return {"action": "allow", "reason": "ignored_administrator"}
    if payload.manage_messages and settings["ignore_moderators"]:
        return {"action": "allow", "reason": "ignored_moderator"}

    excluded_user = (
        await session.execute(
            text("""
                SELECT 1
                FROM plugin_antiflood.user_exceptions
                WHERE guild_id=:guild_id AND user_id=:user_id
            """),
            {"guild_id": payload.guild_id, "user_id": payload.user_id},
        )
    ).scalar_one_or_none()
    if excluded_user:
        return {"action": "allow", "reason": "excluded_user"}

    if payload.role_ids:
        excluded_role = (
            await session.execute(
                text("""
                    SELECT 1
                    FROM plugin_antiflood.role_exceptions
                    WHERE guild_id=:guild_id
                      AND role_id = ANY(CAST(:role_ids AS bigint[]))
                    LIMIT 1
                """),
                {"guild_id": payload.guild_id, "role_ids": payload.role_ids},
            )
        ).scalar_one_or_none()
        if excluded_role:
            return {"action": "allow", "reason": "excluded_role"}

    cooldown = int(rule["cooldown_seconds"])
    params = {
        "guild_id": payload.guild_id,
        "channel_id": payload.channel_id,
        "user_id": payload.user_id,
        "cooldown": cooldown,
    }

    accepted = (
        await session.execute(
            text("""
                INSERT INTO plugin_antiflood.cooldowns(
                    guild_id,channel_id,user_id,last_message_at
                )
                VALUES(:guild_id,:channel_id,:user_id,now())
                ON CONFLICT(guild_id,channel_id,user_id)
                DO UPDATE SET last_message_at=now()
                WHERE plugin_antiflood.cooldowns.last_message_at
                      <= now() - make_interval(secs=>:cooldown)
                RETURNING last_message_at
            """),
            params,
        )
    ).mappings().first()

    if accepted is not None:
        await session.commit()
        logger.info(
            "AntiFlood allow: accepted guild=%s channel=%s user=%s cooldown=%s",
            payload.guild_id, payload.channel_id, payload.user_id, cooldown,
        )
        return {"action": "allow", "reason": "accepted", "cooldown": cooldown}

    remaining = (
        await session.execute(
            text("""
                SELECT GREATEST(
                    1,
                    CEIL(EXTRACT(EPOCH FROM (
                        last_message_at
                        + make_interval(secs=>:cooldown)
                        - now()
                    )))
                )::int
                FROM plugin_antiflood.cooldowns
                WHERE guild_id=:guild_id
                  AND channel_id=:channel_id
                  AND user_id=:user_id
            """),
            params,
        )
    ).scalar_one_or_none()

    await session.rollback()
    remaining_seconds = max(1, int(remaining or cooldown))

    logger.info(
        "AntiFlood delete: cooldown_active guild=%s channel=%s user=%s remaining=%s cooldown=%s",
        payload.guild_id, payload.channel_id, payload.user_id,
        remaining_seconds, cooldown,
    )
    return {
        "action": "delete",
        "reason": "cooldown_active",
        "remaining": remaining_seconds,
        "cooldown": cooldown,
    }
