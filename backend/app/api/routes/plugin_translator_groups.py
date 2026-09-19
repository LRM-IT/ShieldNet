from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.global_languages import GlobalLanguage
from app.models.guild_languages import GuildLanguage
from app.models.plugins import GuildPluginInstallation
from app.core.config import settings

router = APIRouter(tags=["Translator Groups plugin"])
internal_router = APIRouter(
    prefix="/internal/plugin-translator-groups",
    tags=["Internal Translator Groups plugin"],
    dependencies=[Depends(verify_internal_service_token)],
)


class Binding(BaseModel):
    channel_id: str
    language: str = Field(min_length=2, max_length=16)

    @field_validator("channel_id")
    @classmethod
    def discord_id(cls, value: str) -> str:
        if not value.isdigit() or not 15 <= len(value) <= 22:
            raise ValueError("Channel ID must be a Discord ID")
        return value


class Group(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    enabled: bool = True
    channels: list[Binding] = Field(default_factory=list, max_length=25)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Group name is empty")
        return name


class SettingsInput(BaseModel):
    groups: list[Group] = Field(default_factory=list, max_length=30)
    include_source_link: bool = True
    cache_enabled: bool = True
    cache_ttl_hours: int = Field(default=72, ge=1, le=720)
    cache_max_entries: int = Field(default=2000, ge=100, le=50000)
    cache_min_characters: int = Field(default=4, ge=1, le=500)
    max_source_characters: int = Field(default=4000, ge=100, le=12000)
    fallback_to_original: bool = True
    forward_attachments: bool = True
    forward_stickers: bool = True
    protected_terms: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("protected_terms")
    @classmethod
    def clean_protected_terms(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            term = value.strip()
            if not term or term.casefold() in seen:
                continue
            if len(term) > 80:
                raise ValueError("Protected terms cannot exceed 80 characters")
            seen.add(term.casefold())
            result.append(term)
        return result


class GroupCommand(BaseModel):
    guild_id: int
    name: str = Field(min_length=1, max_length=60)


class BindCommand(GroupCommand):
    channel_id: str
    language: str


async def _installation(session: AsyncSession, guild_id: int) -> GuildPluginInstallation | None:
    return await session.scalar(select(GuildPluginInstallation).where(
        GuildPluginInstallation.guild_id == guild_id,
        GuildPluginInstallation.plugin_key == "translator_groups",
    ))


async def _languages(session: AsyncSession, guild_id: int) -> list[dict]:
    rows = (await session.execute(
        select(GlobalLanguage.code, GlobalLanguage.native_name)
        .join(GuildLanguage, GuildLanguage.language_code == GlobalLanguage.code)
        .where(GuildLanguage.guild_id == guild_id, GuildLanguage.enabled.is_(True), GlobalLanguage.is_active.is_(True))
        .order_by(GuildLanguage.sort_order, GlobalLanguage.name)
    )).all()
    return [{"code": code, "name": name} for code, name in rows]


def _validate_groups(groups: list[Group], languages: set[str]) -> None:
    names = [group.name.casefold() for group in groups]
    if len(set(names)) != len(names):
        raise HTTPException(422, "Translation group names must be unique")
    for group in groups:
        channels = [binding.channel_id for binding in group.channels]
        if len(set(channels)) != len(channels):
            raise HTTPException(422, f"Channel is duplicated in group {group.name}")
        if any(binding.language not in languages for binding in group.channels):
            raise HTTPException(422, f"Group {group.name} uses a language not enabled on this server")


async def _settings(session: AsyncSession, guild_id: int) -> dict:
    installation = await _installation(session, guild_id)
    config = installation.configuration or {} if installation else {}
    return {
        "installed": installation is not None,
        "enabled": bool(installation and installation.enabled),
        "groups": config.get("groups", []),
        "include_source_link": config.get("include_source_link", True),
        "cache_enabled": config.get("cache_enabled", True),
        "cache_ttl_hours": config.get("cache_ttl_hours", 72),
        "cache_max_entries": config.get("cache_max_entries", 2000),
        "cache_min_characters": config.get("cache_min_characters", 4),
        "max_source_characters": config.get("max_source_characters", 4000),
        "fallback_to_original": config.get("fallback_to_original", True),
        "forward_attachments": config.get("forward_attachments", True),
        "forward_stickers": config.get("forward_stickers", True),
        "protected_terms": config.get("protected_terms", []),
        "languages": await _languages(session, guild_id),
    }


@router.get("/discord/guilds/{guild_id}/plugins/translator-groups/settings")
async def get_settings(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    return await _settings(session, guild_id)


@router.put("/discord/guilds/{guild_id}/plugins/translator-groups/settings")
async def save_settings(guild_id: int, payload: SettingsInput, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    installation = await _installation(session, guild_id)
    if installation is None:
        raise HTTPException(409, "Install Translator Groups first")
    _validate_groups(payload.groups, {item["code"] for item in await _languages(session, guild_id)})
    installation.configuration = payload.model_dump()
    await session.commit()
    return await _settings(session, guild_id)


@router.get("/discord/guilds/{guild_id}/plugins/translator-groups/cache")
async def cache_stats(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        count = int(await redis.zcard(f"shieldnet:translator-cache-index:{guild_id}"))
        hits = int(await redis.get(f"shieldnet:translator-cache-hits:{guild_id}") or 0)
        misses = int(await redis.get(f"shieldnet:translator-cache-misses:{guild_id}") or 0)
        return {"entries": count, "hits": hits, "misses": misses}
    finally:
        await redis.aclose()


@router.delete("/discord/guilds/{guild_id}/plugins/translator-groups/cache")
async def clear_cache(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    index = f"shieldnet:translator-cache-index:{guild_id}"
    try:
        keys = await redis.zrange(index, 0, -1)
        if keys:
            await redis.delete(*keys)
        await redis.delete(index, f"shieldnet:translator-cache-hits:{guild_id}", f"shieldnet:translator-cache-misses:{guild_id}")
        return {"cleared": len(keys)}
    finally:
        await redis.aclose()


@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_config(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    return await _settings(session, guild_id)


async def _required(session: AsyncSession, guild_id: int) -> GuildPluginInstallation:
    installation = await _installation(session, guild_id)
    if installation is None:
        raise HTTPException(409, "Install Translator Groups first")
    return installation


@internal_router.post("/groups")
async def create_group(payload: GroupCommand, session: AsyncSession = Depends(get_db_session)):
    installation = await _required(session, payload.guild_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Group name is empty")
    config = deepcopy(installation.configuration or {})
    groups = list(config.get("groups", []))
    if any(group["name"].casefold() == name.casefold() for group in groups):
        raise HTTPException(409, "Group already exists")
    if len(groups) >= 30:
        raise HTTPException(422, "Maximum 30 translation groups")
    groups.append({"name": name, "enabled": True, "channels": []})
    installation.configuration = {**config, "groups": groups}
    await session.commit()
    return {"name": name}


@internal_router.post("/bindings")
async def bind_channel(payload: BindCommand, session: AsyncSession = Depends(get_db_session)):
    installation = await _required(session, payload.guild_id)
    binding = Binding(channel_id=payload.channel_id, language=payload.language.strip().lower())
    languages = {item["code"] for item in await _languages(session, payload.guild_id)}
    if binding.language not in languages:
        raise HTTPException(422, "Language is not enabled on this server")
    config = deepcopy(installation.configuration or {})
    groups = list(config.get("groups", []))
    group = next((item for item in groups if item["name"].casefold() == payload.name.strip().casefold()), None)
    if group is None:
        raise HTTPException(404, "Translation group not found")
    channels = [item for item in group["channels"] if item["channel_id"] != binding.channel_id]
    if len(channels) >= 25:
        raise HTTPException(422, "Maximum 25 channels per group")
    group["channels"] = [*channels, binding.model_dump()]
    installation.configuration = {**config, "groups": groups}
    await session.commit()
    return {"group": group["name"], **binding.model_dump()}


@internal_router.delete("/guilds/{guild_id}/groups/{group_name}/channels/{channel_id}")
async def unbind_channel(guild_id: int, group_name: str, channel_id: str, session: AsyncSession = Depends(get_db_session)):
    installation = await _required(session, guild_id)
    config = deepcopy(installation.configuration or {})
    groups = list(config.get("groups", []))
    group = next((item for item in groups if item["name"].casefold() == group_name.casefold()), None)
    if group is None:
        raise HTTPException(404, "Translation group not found")
    channels = [item for item in group["channels"] if item["channel_id"] != channel_id]
    if len(channels) == len(group["channels"]):
        raise HTTPException(404, "Channel is not bound to this group")
    group["channels"] = channels
    installation.configuration = {**config, "groups": groups}
    await session.commit()
    return {"removed": True}
