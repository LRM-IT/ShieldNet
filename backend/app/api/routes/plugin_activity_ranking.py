from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.members import DiscordMember
from app.models.plugins import GuildPluginInstallation

router = APIRouter(tags=["Activity & Ranking plugin"])
internal_router = APIRouter(prefix="/internal/plugin-activity-ranking", tags=["Internal Activity & Ranking"], dependencies=[Depends(verify_internal_service_token)])


class SettingsInput(BaseModel):
    message_points: int = Field(default=1, ge=0, le=1000)
    voice_points_per_minute: float = Field(default=0.2, ge=0, le=1000)
    message_cooldown_seconds: int = Field(default=60, ge=0, le=3600)
    excluded_channel_ids: list[str] = Field(default_factory=list, max_length=100)
    excluded_role_ids: list[str] = Field(default_factory=list, max_length=100)


class ActivityInput(BaseModel):
    guild_id: int
    discord_user_id: int
    kind: str
    amount: float = Field(default=1, ge=0, le=100000)
    channel_id: str | None = None
    role_ids: list[str] = Field(default_factory=list)


async def installation(session: AsyncSession, guild_id: int, lock: bool = False):
    query = select(GuildPluginInstallation).where(GuildPluginInstallation.guild_id == guild_id, GuildPluginInstallation.plugin_key == "activity_ranking")
    return await session.scalar(query.with_for_update() if lock else query)


def config(item) -> dict:
    raw = item.configuration or {} if item else {}
    return {
        "message_points": int(raw.get("message_points", 1)),
        "voice_points_per_minute": float(raw.get("voice_points_per_minute", .2)),
        "message_cooldown_seconds": int(raw.get("message_cooldown_seconds", 60)),
        "excluded_channel_ids": raw.get("excluded_channel_ids", []),
        "excluded_role_ids": raw.get("excluded_role_ids", []),
    }


async def leaderboard(session: AsyncSession, guild_id: int, item, limit: int = 100) -> list[dict]:
    scores = (item.configuration or {}).get("scores", {}) if item else {}
    members = (await session.execute(select(DiscordMember).where(DiscordMember.guild_id == guild_id, DiscordMember.discord_user_id.in_([int(key) for key in scores] or [0])))).scalars().all()
    names = {str(member.discord_user_id): member.global_name or member.username for member in members}
    rows = [{"discord_user_id": user_id, "name": names.get(user_id, f"User {user_id}"), **values} for user_id, values in scores.items()]
    rows.sort(key=lambda value: (-float(value.get("points", 0)), value["name"].casefold()))
    return [{"rank": index + 1, **value} for index, value in enumerate(rows[:limit])]


@router.get("/discord/guilds/{guild_id}/plugins/activity-ranking/settings")
async def get_settings(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    item = await installation(session, guild_id)
    return {"installed": item is not None, "enabled": bool(item and item.enabled), **config(item), "leaderboard": await leaderboard(session, guild_id, item)}


@router.put("/discord/guilds/{guild_id}/plugins/activity-ranking/settings")
async def save_settings(guild_id: int, payload: SettingsInput, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    item = await installation(session, guild_id, True)
    if not item:
        raise HTTPException(409, "Install Activity & Ranking first")
    item.configuration = {**(item.configuration or {}), **payload.model_dump()}
    await session.commit()
    return await get_settings(guild_id, user, session)


@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_config(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    item = await installation(session, guild_id)
    return {"enabled": bool(item and item.enabled), **config(item)}


@internal_router.get("/guilds/{guild_id}/leaderboard")
async def internal_leaderboard(guild_id: int, limit: int = Query(default=10, ge=1, le=25), session: AsyncSession = Depends(get_db_session)):
    item = await installation(session, guild_id)
    return {"enabled": bool(item and item.enabled), "leaderboard": await leaderboard(session, guild_id, item, limit)}


@internal_router.post("/activity")
async def activity(payload: ActivityInput, session: AsyncSession = Depends(get_db_session)):
    if payload.kind not in {"message", "voice"}:
        raise HTTPException(422, "Unsupported activity kind")
    item = await installation(session, payload.guild_id, True)
    if not item or not item.enabled:
        return {"recorded": False}
    settings = config(item)
    if payload.channel_id in settings["excluded_channel_ids"] or set(payload.role_ids) & set(settings["excluded_role_ids"]):
        return {"recorded": False}
    points = settings["message_points"] * payload.amount if payload.kind == "message" else settings["voice_points_per_minute"] * payload.amount
    data = dict(item.configuration or {})
    scores = dict(data.get("scores") or {})
    user_id = str(payload.discord_user_id)
    score = dict(scores.get(user_id) or {"points": 0, "messages": 0, "voice_minutes": 0})
    score["points"] = round(float(score.get("points", 0)) + points, 2)
    if payload.kind == "message": score["messages"] = int(score.get("messages", 0)) + int(payload.amount)
    else: score["voice_minutes"] = round(float(score.get("voice_minutes", 0)) + payload.amount, 1)
    scores[user_id] = score
    item.configuration = {**data, "scores": scores}
    await session.commit()
    return {"recorded": True, "score": score}
