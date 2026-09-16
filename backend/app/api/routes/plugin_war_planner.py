from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.plugins import GuildPluginInstallation
from app.models.role_channel_management import DiscordStructureChange

router = APIRouter(tags=["War Planner plugin"])
internal_router = APIRouter(
    prefix="/internal/plugin-war-planner",
    tags=["Internal War Planner"],
    dependencies=[Depends(verify_internal_service_token)],
)


class WaveInput(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=60)
    starts_at: datetime
    capacity: int = Field(default=0, ge=0, le=1000)
    targets: str = Field(default="", max_length=2000)

    @field_validator("starts_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class WarInput(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=100)
    opponent: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=2000)
    channel_id: str
    enabled: bool = True
    waves: list[WaveInput] = Field(default_factory=list, max_length=25)


class SettingsInput(BaseModel):
    wars: list[WarInput] = Field(default_factory=list, max_length=50)


class PublishInput(BaseModel):
    war_id: str


class PanelResult(BaseModel):
    guild_id: int
    war_id: str
    channel_id: str
    message_id: str


class SignupInput(BaseModel):
    guild_id: int
    war_id: str
    wave_id: str | None = None
    discord_user_id: int


def rows(item: GuildPluginInstallation | None) -> list[dict]:
    return [dict(value) for value in ((item.configuration or {}).get("wars", []) if item else [])]


async def installation(session: AsyncSession, guild_id: int, lock: bool = False):
    query = select(GuildPluginInstallation).where(
        GuildPluginInstallation.guild_id == guild_id,
        GuildPluginInstallation.plugin_key == "war_planner",
    )
    return await session.scalar(query.with_for_update() if lock else query)


async def response(session: AsyncSession, guild_id: int) -> dict:
    item = await installation(session, guild_id)
    return {"installed": item is not None, "enabled": bool(item and item.enabled), "wars": rows(item)}


@router.get("/discord/guilds/{guild_id}/plugins/war-planner/settings")
async def get_settings(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    return await response(session, guild_id)


@router.put("/discord/guilds/{guild_id}/plugins/war-planner/settings")
async def save_settings(guild_id: int, payload: SettingsInput, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    item = await installation(session, guild_id, True)
    if not item:
        raise HTTPException(409, "Install War Planner first")
    previous = {war["id"]: war for war in rows(item)}
    saved = []
    for war in payload.wars:
        data = war.model_dump(mode="json")
        old = previous.get(war.id) or {}
        data["message_id"] = old.get("message_id")
        data["assignments"] = old.get("assignments", {})
        saved.append(data)
    item.configuration = {**(item.configuration or {}), "wars": saved}
    await session.commit()
    return await response(session, guild_id)


@router.post("/discord/guilds/{guild_id}/plugins/war-planner/publish")
async def publish(guild_id: int, payload: PublishInput, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    item = await installation(session, guild_id)
    war = next((value for value in rows(item) if value["id"] == payload.war_id and value.get("enabled")), None)
    if not item or not item.enabled:
        raise HTTPException(409, "Enable War Planner first")
    if not war:
        raise HTTPException(404, "War plan not found")
    job = DiscordStructureChange(
        guild_id=guild_id,
        object_type="war_plan_panel",
        operation="publish",
        payload={"war_id": war["id"]},
        preview={"safe_to_apply": True},
        status="pending",
        requested_by=user.id,
    )
    session.add(job)
    await session.commit()
    return {"job_id": str(job.id)}


@router.get("/discord/guilds/{guild_id}/plugins/war-planner/jobs/{job_id}")
async def job(guild_id: int, job_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    item = await session.get(DiscordStructureChange, job_id)
    if not item or item.guild_id != guild_id or item.object_type != "war_plan_panel":
        raise HTTPException(404, "Job not found")
    return {"status": item.status, "error": item.result_message}


@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_config(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    return await response(session, guild_id)


@internal_router.post("/panel")
async def panel(payload: PanelResult, session: AsyncSession = Depends(get_db_session)):
    item = await installation(session, payload.guild_id, True)
    wars = rows(item)
    war = next((value for value in wars if value["id"] == payload.war_id), None)
    if not war or war.get("channel_id") != payload.channel_id:
        raise HTTPException(422, "War channel mismatch")
    war["message_id"] = payload.message_id
    item.configuration = {**(item.configuration or {}), "wars": wars}
    await session.commit()
    return {"ok": True}


@internal_router.post("/signup")
async def signup(payload: SignupInput, session: AsyncSession = Depends(get_db_session)):
    item = await installation(session, payload.guild_id, True)
    wars = rows(item)
    war = next((value for value in wars if value["id"] == payload.war_id and value.get("enabled")), None)
    if not item or not item.enabled or not war:
        raise HTTPException(404, "War plan unavailable")
    assignments = dict(war.get("assignments") or {})
    user_id = str(payload.discord_user_id)
    if payload.wave_id is None:
        assignments.pop(user_id, None)
    else:
        wave = next((value for value in war.get("waves", []) if value["id"] == payload.wave_id), None)
        if not wave:
            raise HTTPException(404, "Wave not found")
        used = sum(value == payload.wave_id for key, value in assignments.items() if key != user_id)
        if wave.get("capacity") and used >= int(wave["capacity"]):
            raise HTTPException(409, "Wave is full")
        assignments[user_id] = payload.wave_id
    war["assignments"] = assignments
    item.configuration = {**(item.configuration or {}), "wars": wars}
    await session.commit()
    return {"assignments": assignments}
