from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.global_languages import GlobalLanguage
from app.models.guild_languages import GuildLanguage
from app.models.plugins import GuildPluginInstallation

router = APIRouter(tags=["First Introduction plugin"])
internal_router = APIRouter(
    prefix="/internal/plugin-first-introduction",
    tags=["Internal First Introduction plugin"],
    dependencies=[Depends(verify_internal_service_token)],
)

DEFAULT_CONFIG = {
    "server_numbers": [],
    "nickname_template": "[{alliance}] {nick}",
    "verified_role_id": None,
    "language_roles": {},
}
ALLOWED_FIELDS = {"server", "alliance", "nick"}


class SettingsInput(BaseModel):
    server_numbers: list[str] = Field(default_factory=list, max_length=25)
    nickname_template: str = Field(default="[{alliance}] {nick}", min_length=1, max_length=100)
    verified_role_id: str | None = None
    language_roles: dict[str, str] = Field(default_factory=dict)

    @field_validator("server_numbers")
    @classmethod
    def validate_servers(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value or len(value) > 32 for value in cleaned) or len(set(cleaned)) != len(cleaned):
            raise ValueError("Server numbers must be unique, nonempty and at most 32 characters")
        return cleaned

    @field_validator("nickname_template")
    @classmethod
    def validate_template(cls, value: str) -> str:
        fields = re.findall(r"\{([^{}]+)\}", value)
        if not set(fields) <= ALLOWED_FIELDS or "nick" not in fields or value.count("{") != len(fields) or value.count("}") != len(fields):
            raise ValueError("Use only {server}, {alliance}, {nick}; {nick} is required")
        return value

    @field_validator("verified_role_id")
    @classmethod
    def validate_id(cls, value: str | None) -> str | None:
        if value is not None and (not value.isdigit() or not 15 <= len(value) <= 22):
            raise ValueError("Discord ID must be a 15-22 digit string")
        return value

    @field_validator("language_roles")
    @classmethod
    def validate_language_roles(cls, values: dict[str, str]) -> dict[str, str]:
        if any(not role_id.isdigit() or not 15 <= len(role_id) <= 22 for role_id in values.values()):
            raise ValueError("Language role IDs must be Discord ID strings")
        return values

class CompletionInput(BaseModel):
    guild_id: int
    discord_user_id: int
    language_code: str = Field(min_length=2, max_length=16)
    server_number: str = Field(min_length=1, max_length=32)
    alliance: str = Field(min_length=1, max_length=32)
    nickname: str = Field(min_length=1, max_length=64)
    applied_nickname: str = Field(min_length=1, max_length=32)


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
    config = {**DEFAULT_CONFIG, **(installation.configuration or {} if installation else {})}
    languages = await _languages(session, guild_id)
    return {
        **config,
        "installed": installation is not None,
        "enabled": bool(installation and installation.enabled),
        "languages": languages,
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
        raise HTTPException(409, "Install First Introduction before configuring it")
    languages = {item["code"] for item in await _languages(session, guild_id)}
    if not languages or len(languages) > 25:
        raise HTTPException(422, "Configure 1-25 server languages first")
    if set(payload.language_roles) != languages:
        raise HTTPException(422, "Choose one role for every enabled server language")
    if not payload.server_numbers:
        raise HTTPException(422, "Add at least one server number")
    if payload.verified_role_id is None:
        raise HTTPException(422, "Choose a verified role")
    installation.configuration = payload.model_dump()
    await session.commit()
    return await _settings(session, guild_id)


@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_config(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    return await _settings(session, guild_id)


@internal_router.get("/guilds/{guild_id}/members/{user_id}")
async def member_status(guild_id: int, user_id: int, session: AsyncSession = Depends(get_db_session)):
    row = await session.scalar(text(
        "SELECT 1 FROM discord.first_introduction_profiles WHERE guild_id=:guild_id AND discord_user_id=:user_id"
    ), {"guild_id": guild_id, "user_id": user_id})
    return {"completed": row is not None}


@internal_router.post("/complete")
async def complete(payload: CompletionInput, session: AsyncSession = Depends(get_db_session)):
    settings = await _settings(session, payload.guild_id)
    if not settings["enabled"]:
        raise HTTPException(409, "Plugin is disabled")
    if payload.server_number not in settings["server_numbers"] or payload.language_code not in {item["code"] for item in settings["languages"]}:
        raise HTTPException(422, "Language or server number is no longer configured")
    await session.execute(text("""
        INSERT INTO discord.first_introduction_profiles
        (guild_id, discord_user_id, language_code, server_number, alliance, nickname, applied_nickname, completed_at)
        VALUES (:guild_id, :discord_user_id, :language_code, :server_number, :alliance, :nickname, :applied_nickname, now())
        ON CONFLICT (guild_id, discord_user_id) DO NOTHING
    """), payload.model_dump())
    await session.commit()
    return {"completed": True}
