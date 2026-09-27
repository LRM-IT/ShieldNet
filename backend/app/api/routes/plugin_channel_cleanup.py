from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.plugins import GuildPluginInstallation

router = APIRouter(tags=["Channel Cleanup plugin"])
internal_router = APIRouter(
    prefix="/internal/plugin-channel-cleanup",
    tags=["Internal Channel Cleanup"],
    dependencies=[Depends(verify_internal_service_token)],
)


class CleanupTarget(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    channel_id: str = Field(pattern=r"^\d{15,22}$")
    retention_days: int = Field(default=30, ge=1, le=3650)
    keep_pinned: bool = True
    enabled: bool = True


class SettingsInput(BaseModel):
    interval_hours: int = Field(default=24, ge=1, le=168)
    targets: list[CleanupTarget] = Field(default_factory=list, max_length=100)


class CleanupResult(BaseModel):
    run_id: str
    deleted_messages: int = Field(ge=0)
    scanned_channels: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list, max_length=100)


async def installation(session: AsyncSession, guild_id: int, lock: bool = False):
    query = select(GuildPluginInstallation).where(
        GuildPluginInstallation.guild_id == guild_id,
        GuildPluginInstallation.plugin_key == "channel_cleanup",
    )
    if lock:
        query = query.with_for_update()
    return await session.scalar(query)


def public_response(item: GuildPluginInstallation | None) -> dict:
    config = dict(item.configuration or {}) if item else {}
    return {
        "installed": item is not None,
        "enabled": bool(item and item.enabled),
        "interval_hours": int(config.get("interval_hours") or 24),
        "targets": list(config.get("targets") or []),
        "last_run_at": config.get("last_run_at"),
        "last_result": config.get("last_result"),
        "run_pending": bool(config.get("run_requested_at") or config.get("run_started_at")),
    }


@router.get("/discord/guilds/{guild_id}/plugins/channel-cleanup/settings")
async def get_settings(
    guild_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_module(session, user, guild_id, "plugins")
    return public_response(await installation(session, guild_id))


@router.put("/discord/guilds/{guild_id}/plugins/channel-cleanup/settings")
async def save_settings(
    guild_id: int,
    payload: SettingsInput,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_module(session, user, guild_id, "plugins")
    item = await installation(session, guild_id, True)
    if not item:
        raise HTTPException(409, "Install Channel Cleanup first")
    channel_ids = [target.channel_id for target in payload.targets]
    if len(channel_ids) != len(set(channel_ids)):
        raise HTTPException(422, "A channel can only be added once")
    item.configuration = {
        **(item.configuration or {}),
        "interval_hours": payload.interval_hours,
        "targets": [target.model_dump() for target in payload.targets],
    }
    await session.commit()
    return public_response(item)


@router.post("/discord/guilds/{guild_id}/plugins/channel-cleanup/run")
async def request_run(
    guild_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_module(session, user, guild_id, "plugins")
    item = await installation(session, guild_id, True)
    if not item or not item.enabled:
        raise HTTPException(409, "Enable Channel Cleanup first")
    config = dict(item.configuration or {})
    if not any(target.get("enabled", True) for target in config.get("targets") or []):
        raise HTTPException(422, "Add at least one enabled cleanup target")
    config["run_requested_at"] = datetime.now(UTC).isoformat()
    item.configuration = config
    await session.commit()
    return {"queued": True}


@internal_router.post("/guilds/{guild_id}/claim")
async def claim_run(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    item = await installation(session, guild_id, True)
    if not item or not item.enabled:
        return {"claimed": False}
    config = dict(item.configuration or {})
    targets = [target for target in config.get("targets") or [] if target.get("enabled", True)]
    if not targets:
        return {"claimed": False}
    now = datetime.now(UTC)
    started_raw = config.get("run_started_at")
    if started_raw:
        try:
            started = datetime.fromisoformat(str(started_raw).replace("Z", "+00:00"))
            if now - started < timedelta(minutes=30):
                return {"claimed": False}
        except ValueError:
            pass
    requested = bool(config.get("run_requested_at"))
    last_raw = config.get("last_run_at")
    due = not last_raw
    if last_raw:
        try:
            last = datetime.fromisoformat(str(last_raw).replace("Z", "+00:00"))
            due = now >= last + timedelta(hours=int(config.get("interval_hours") or 24))
        except ValueError:
            due = True
    if not requested and not due:
        return {"claimed": False}
    run_id = str(uuid4())
    config["run_started_at"] = now.isoformat()
    config["run_id"] = run_id
    config.pop("run_requested_at", None)
    item.configuration = config
    await session.commit()
    return {"claimed": True, "run_id": run_id, "targets": targets}


@internal_router.post("/guilds/{guild_id}/result")
async def save_result(guild_id: int, payload: CleanupResult, session: AsyncSession = Depends(get_db_session)):
    item = await installation(session, guild_id, True)
    if not item:
        raise HTTPException(404, "Channel Cleanup is not installed")
    config = dict(item.configuration or {})
    if config.get("run_id") != payload.run_id:
        raise HTTPException(409, "Cleanup run is no longer current")
    finished = datetime.now(UTC).isoformat()
    config["last_run_at"] = finished
    config["last_result"] = {
        "finished_at": finished,
        "deleted_messages": payload.deleted_messages,
        "scanned_channels": payload.scanned_channels,
        "errors": payload.errors,
    }
    config.pop("run_started_at", None)
    config.pop("run_id", None)
    item.configuration = config
    await session.commit()
    return {"ok": True}
