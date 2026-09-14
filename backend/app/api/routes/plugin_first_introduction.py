from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.global_languages import GlobalLanguage
from app.models.guild_languages import GuildLanguage
from app.models.plugins import GuildPluginInstallation

router = APIRouter(tags=["Language Selection plugin"])
internal_router = APIRouter(
    prefix="/internal/plugin-first-introduction",
    tags=["Internal Language Selection plugin"],
    dependencies=[Depends(verify_internal_service_token)],
)


class SettingsInput(BaseModel):
    language_roles: dict[str, str] = Field(default_factory=dict)
    channel_id: str | None = None

    @field_validator("language_roles")
    @classmethod
    def validate_language_roles(cls, values: dict[str, str]) -> dict[str, str]:
        if any(not role_id.isdigit() or not 15 <= len(role_id) <= 22 for role_id in values.values()):
            raise ValueError("Language role IDs must be Discord ID strings")
        if len(set(values.values())) != len(values):
            raise ValueError("Each language needs its own Discord role")
        return values

    @field_validator("channel_id")
    @classmethod
    def validate_channel_id(cls, value: str | None) -> str | None:
        if value is not None and (not value.isdigit() or not 15 <= len(value) <= 22):
            raise ValueError("Thread or channel ID must be a Discord ID")
        return value


class PanelInput(BaseModel):
    guild_id: int
    channel_id: str
    message_id: str


async def _installation(session: AsyncSession, guild_id: int) -> GuildPluginInstallation | None:
    return await session.scalar(select(GuildPluginInstallation).where(
        GuildPluginInstallation.guild_id == guild_id,
        GuildPluginInstallation.plugin_key == "first_introduction",
    ))


async def _languages(session: AsyncSession, guild_id: int) -> list[dict]:
    rows = (await session.execute(
        select(GlobalLanguage.code, GlobalLanguage.native_name, GlobalLanguage.flag)
        .join(GuildLanguage, GuildLanguage.language_code == GlobalLanguage.code)
        .where(GuildLanguage.guild_id == guild_id, GuildLanguage.enabled.is_(True), GlobalLanguage.is_active.is_(True))
        .order_by(GuildLanguage.sort_order, GlobalLanguage.name)
    )).all()
    return [{"code": code, "name": name, "flag": flag} for code, name, flag in rows]


async def _settings(session: AsyncSession, guild_id: int) -> dict:
    installation = await _installation(session, guild_id)
    configuration = installation.configuration or {} if installation else {}
    return {
        "installed": installation is not None,
        "enabled": bool(installation and installation.enabled),
        "languages": await _languages(session, guild_id),
        "language_roles": configuration.get("language_roles", {}),
        "channel_id": configuration.get("channel_id"),
        "message_id": configuration.get("message_id"),
    }


@router.get("/discord/guilds/{guild_id}/plugins/first-introduction/settings")
async def get_settings(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    return await _settings(session, guild_id)


@router.put("/discord/guilds/{guild_id}/plugins/first-introduction/settings")
async def save_settings(guild_id: int, payload: SettingsInput, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    installation = await _installation(session, guild_id)
    if installation is None:
        raise HTTPException(409, "Install Language Selection before configuring it")
    languages = {item["code"] for item in await _languages(session, guild_id)}
    if not languages or len(languages) > 25:
        raise HTTPException(422, "Configure 1-25 server languages first")
    if set(payload.language_roles) != languages:
        raise HTTPException(422, "Choose one role for every enabled server language")
    configured = await _languages(session, guild_id)
    flags = [item["flag"] for item in configured]
    if any(not flag for flag in flags) or len(set(flags)) != len(flags):
        raise HTTPException(422, "Each server language needs a unique flag in the language catalogue")
    if payload.channel_id is None:
        raise HTTPException(422, "Choose a thread or text channel")
    previous = installation.configuration or {}
    installation.configuration = {
        **payload.model_dump(),
        "message_id": previous.get("message_id") if previous.get("channel_id") == payload.channel_id
        and previous.get("language_roles") == payload.language_roles else None,
    }
    await session.commit()
    return await _settings(session, guild_id)


@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_config(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    return await _settings(session, guild_id)


@internal_router.post("/panel")
async def internal_panel(payload: PanelInput, session: AsyncSession = Depends(get_db_session)):
    installation = await _installation(session, payload.guild_id)
    if not installation or not installation.enabled:
        raise HTTPException(409, "Language Selection is disabled")
    configuration = installation.configuration or {}
    if configuration.get("channel_id") != payload.channel_id:
        raise HTTPException(422, "Panel channel does not match configuration")
    installation.configuration = {**configuration, "message_id": payload.message_id}
    await session.commit()
    return {"message_id": payload.message_id}
