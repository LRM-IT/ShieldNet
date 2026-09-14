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

    @field_validator("language_roles")
    @classmethod
    def validate_language_roles(cls, values: dict[str, str]) -> dict[str, str]:
        if any(not role_id.isdigit() or not 15 <= len(role_id) <= 22 for role_id in values.values()):
            raise ValueError("Language role IDs must be Discord ID strings")
        if len(set(values.values())) != len(values):
            raise ValueError("Each language needs its own Discord role")
        return values


async def _installation(session: AsyncSession, guild_id: int) -> GuildPluginInstallation | None:
    return await session.scalar(select(GuildPluginInstallation).where(
        GuildPluginInstallation.guild_id == guild_id,
        GuildPluginInstallation.plugin_key == "first_introduction",
    ))


async def _languages(session: AsyncSession, guild_id: int) -> list[dict]:
    rows = (await session.execute(
        select(GlobalLanguage.code, GlobalLanguage.native_name)
        .join(GuildLanguage, GuildLanguage.language_code == GlobalLanguage.code)
        .where(GuildLanguage.guild_id == guild_id, GuildLanguage.enabled.is_(True), GlobalLanguage.is_active.is_(True))
        .order_by(GuildLanguage.sort_order, GlobalLanguage.name)
    )).all()
    return [{"code": code, "name": name} for code, name in rows]


async def _settings(session: AsyncSession, guild_id: int) -> dict:
    installation = await _installation(session, guild_id)
    configuration = installation.configuration or {} if installation else {}
    return {
        "installed": installation is not None,
        "enabled": bool(installation and installation.enabled),
        "languages": await _languages(session, guild_id),
        "language_roles": configuration.get("language_roles", {}),
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
    installation.configuration = payload.model_dump()
    await session.commit()
    return await _settings(session, guild_id)


@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_config(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    return await _settings(session, guild_id)
