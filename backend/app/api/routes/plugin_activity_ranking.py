from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response
from pathlib import Path
from io import BytesIO
from uuid import uuid4, UUID
from PIL import Image, ImageOps
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


class RewardRoleInput(BaseModel):
    level: int = Field(ge=2, le=10000)
    role_id: str = Field(min_length=1, max_length=32)


class SettingsInput(BaseModel):
    message_points: int = Field(default=1, ge=0, le=1000)
    voice_points_per_minute: float = Field(default=0.2, ge=0, le=1000)
    message_cooldown_seconds: int = Field(default=60, ge=0, le=3600)
    excluded_channel_ids: list[str] = Field(default_factory=list, max_length=100)
    excluded_role_ids: list[str] = Field(default_factory=list, max_length=100)
    level_base_points: int = Field(default=100, ge=1, le=1000000)
    level_growth: float = Field(default=1.5, ge=1, le=5)
    reward_roles: list[RewardRoleInput] = Field(default_factory=list, max_length=100)
    announce_level_up: bool = True
    announce_in_reply: bool = True
    announce_in_dm: bool = False
    announce_in_channel: bool = False
    announcement_channel_id: str | None = Field(default=None, max_length=32)
    announcement_message: str = Field(default="🎉 {member} reached level {level}!", min_length=1, max_length=500)


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
        "background_id": raw.get("background_id"),
        "message_points": int(raw.get("message_points", 1)),
        "voice_points_per_minute": float(raw.get("voice_points_per_minute", .2)),
        "message_cooldown_seconds": int(raw.get("message_cooldown_seconds", 60)),
        "excluded_channel_ids": raw.get("excluded_channel_ids", []),
        "excluded_role_ids": raw.get("excluded_role_ids", []),
        "level_base_points": int(raw.get("level_base_points", 100)),
        "level_growth": float(raw.get("level_growth", 1.5)),
        "reward_roles": raw.get("reward_roles", []),
        "announce_level_up": bool(raw.get("announce_level_up", True)),
        "announce_in_reply": bool(raw.get("announce_in_reply", not raw.get("announcement_channel_id"))),
        "announce_in_dm": bool(raw.get("announce_in_dm", False)),
        "announce_in_channel": bool(raw.get("announce_in_channel", bool(raw.get("announcement_channel_id")))),
        "announcement_channel_id": raw.get("announcement_channel_id"),
        "announcement_message": str(raw.get("announcement_message", "🎉 {member} reached level {level}!")),
    }


def level_for(points: float, settings: dict) -> int:
    base = max(1, settings["level_base_points"])
    growth = max(1.0, settings["level_growth"])
    return max(1, int((max(0.0, points) / base) ** (1 / growth)) + 1)


def level_progress(points: float, settings: dict) -> dict:
    level = level_for(points, settings)
    target = max(1, settings["level_base_points"]) * level ** max(1.0, settings["level_growth"])
    remaining = max(0.0, target - points)
    per_message = settings["message_points"]
    return {"next_level": level + 1, "xp_to_next_level": round(remaining, 2),
            "messages_to_next_level": max(1, math.ceil(remaining / per_message)) if per_message > 0 else None}


async def leaderboard(session: AsyncSession, guild_id: int, item, limit: int = 100) -> list[dict]:
    scores = (item.configuration or {}).get("scores", {}) if item else {}
    members = (await session.execute(select(DiscordMember).where(DiscordMember.guild_id == guild_id, DiscordMember.discord_user_id.in_([int(key) for key in scores] or [0])))).scalars().all()
    names = {str(member.discord_user_id): member.global_name or member.username for member in members}
    settings = config(item)
    rows = [{"discord_user_id": user_id, "name": names.get(user_id, f"User {user_id}"), **values, **level_progress(float(values.get("points", 0)), settings), "level": level_for(float(values.get("points", 0)), settings)} for user_id, values in scores.items()]
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
    values = payload.model_dump()
    values["reward_roles"] = sorted(values["reward_roles"], key=lambda reward: reward["level"])
    item.configuration = {**(item.configuration or {}), **values}
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
    previous_level = level_for(float(score.get("points", 0)), settings)
    score["points"] = round(float(score.get("points", 0)) + points, 2)
    if payload.kind == "message": score["messages"] = int(score.get("messages", 0)) + int(payload.amount)
    else: score["voice_minutes"] = round(float(score.get("voice_minutes", 0)) + payload.amount, 1)
    scores[user_id] = score
    item.configuration = {**data, "scores": scores}
    await session.commit()
    level = level_for(float(score.get("points", 0)), settings)
    reward_role_ids = [str(reward.get("role_id")) for reward in settings["reward_roles"] if reward.get("role_id") and int(reward.get("level", 0)) <= level]
    return {
        "recorded": True,
        "background_id": settings.get("background_id"),
        "score": {**score, "level": level},
        "leveled_up": level > previous_level,
        "reward_role_ids": reward_role_ids,
        "announce_level_up": settings["announce_level_up"],
        "announce_in_reply": settings["announce_in_reply"],
        "announce_in_dm": settings["announce_in_dm"],
        "announce_in_channel": settings["announce_in_channel"],
        "announcement_channel_id": settings["announcement_channel_id"],
        "announcement_message": settings["announcement_message"],
    }


BACKGROUND_ROOT = Path("/var/lib/shieldnet/templates/level-backgrounds")


def normalize_background(content: bytes) -> bytes:
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"} or image.width * image.height > 20_000_000:
                raise ValueError("Unsupported image")
            image = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (1200, 400), method=Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, "JPEG", quality=92)
            return output.getvalue()
    except Exception as exc:
        raise HTTPException(422, "Upload a valid PNG, JPEG or WebP image (up to 20 megapixels)") from exc


@router.post("/discord/guilds/{guild_id}/plugins/activity-ranking/background")
async def upload_background(guild_id: int, file: UploadFile = File(...), user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    content = await file.read(8 * 1024 * 1024 + 1)
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(422, "Maximum image size is 8 MB")
    content = normalize_background(content)
    item = await installation(session, guild_id, True)
    if not item:
        raise HTTPException(409, "Install Activity & Ranking first")
    folder = BACKGROUND_ROOT / str(guild_id)
    folder.mkdir(parents=True, exist_ok=True)
    background_id = str(uuid4())
    old = (item.configuration or {}).get("background_id")
    path = folder / f"{background_id}.jpg"
    path.write_bytes(content)
    try:
        item.configuration = {**(item.configuration or {}), "background_id": background_id}
        await session.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    if old:
        (folder / f"{UUID(old)}.jpg").unlink(missing_ok=True)
    return {"background_id": background_id}


@router.delete("/discord/guilds/{guild_id}/plugins/activity-ranking/background")
async def reset_background(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    item = await installation(session, guild_id, True)
    if not item:
        raise HTTPException(404, "Plugin not found")
    old = (item.configuration or {}).get("background_id")
    item.configuration = {**(item.configuration or {}), "background_id": None}
    await session.commit()
    if old:
        (BACKGROUND_ROOT / str(guild_id) / f"{UUID(old)}.jpg").unlink(missing_ok=True)
    return {"background_id": None}


async def background_response(guild_id: int, session: AsyncSession):
    item = await installation(session, guild_id)
    background_id = (item.configuration or {}).get("background_id") if item else None
    if not background_id:
        raise HTTPException(404, "Background not found")
    path = BACKGROUND_ROOT / str(guild_id) / f"{UUID(background_id)}.jpg"
    if not path.exists():
        raise HTTPException(404, "Background not found")
    return Response(path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/discord/guilds/{guild_id}/plugins/activity-ranking/background")
async def get_background(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    return await background_response(guild_id, session)


@internal_router.get("/guilds/{guild_id}/background")
async def internal_background(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    return await background_response(guild_id, session)
