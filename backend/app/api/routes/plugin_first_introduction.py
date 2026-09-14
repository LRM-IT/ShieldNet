from __future__ import annotations

import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.global_languages import GlobalLanguage
from app.models.guild_languages import GuildLanguage
from app.models.guild_roles import DiscordGuildRole
from app.models.plugins import GuildPluginInstallation
from app.models.role_channel_management import DiscordStructureChange

router = APIRouter(tags=["Language Selection plugin"])
internal_router = APIRouter(
    prefix="/internal/plugin-first-introduction",
    tags=["Internal Language Selection plugin"],
    dependencies=[Depends(verify_internal_service_token)],
)

DEFAULT_GROUPS = ({"id": "language-1", "name": "Основна група", "enabled": True},)
ROLE_ID = re.compile(r"^[0-9]{15,22}$")
GROUP_ID = re.compile(r"^[a-z0-9_-]{1,32}$")


class GroupInput(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    channel_id: str | None = None
    access_role_id: str | None = None
    role_name_mask: str = Field(default="{group} - {name}", min_length=1, max_length=100)
    language_roles: dict[str, str] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        value = value.strip().lower()
        if not GROUP_ID.fullmatch(value):
            raise ValueError("Group ID may contain lowercase letters, digits, _ and -")
        return value

    @field_validator("channel_id", "access_role_id")
    @classmethod
    def valid_discord_id(cls, value: str | None) -> str | None:
        if value is not None and not ROLE_ID.fullmatch(value):
            raise ValueError("Use a Discord channel or role ID")
        return value

    @field_validator("language_roles")
    @classmethod
    def valid_language_roles(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not ROLE_ID.fullmatch(role_id) for role_id in value.values()):
            raise ValueError("Language role IDs must be Discord IDs")
        if len(set(value.values())) != len(value):
            raise ValueError("Each language in a group needs a distinct role")
        return value


class SettingsInput(BaseModel):
    groups: list[GroupInput] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_groups(self):
        if len({group.id for group in self.groups}) != len(self.groups):
            raise ValueError("Group IDs must be unique")
        channels = [group.channel_id for group in self.groups if group.enabled and group.channel_id]
        if len(channels) != len(set(channels)):
            raise ValueError("Each enabled group needs its own channel or thread")
        role_ids = [role_id for group in self.groups for role_id in group.language_roles.values()]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("A language role cannot be shared between groups")
        return self


class RoleProvisionInput(BaseModel):
    group_id: str
    role_name_mask: str = Field(min_length=1, max_length=100)


class PanelInput(BaseModel):
    guild_id: int
    group_id: str = "r1"
    channel_id: str
    message_id: str


def _default_groups() -> list[dict]:
    return [{**group, "channel_id": None, "access_role_id": None,
             "role_name_mask": "{group} - {name}", "language_roles": {},
             "message_id": None} for group in DEFAULT_GROUPS]


def _groups(configuration: dict) -> list[dict]:
    if isinstance(configuration.get("groups"), list):
        return [dict(group) for group in configuration["groups"]]
    if any(key in configuration for key in ("channel_id", "language_roles", "message_id")):
        legacy = [{**_default_groups()[0], "id": "r1", "name": "R1"}]
        legacy[0].update({
            "channel_id": configuration.get("channel_id"),
            "language_roles": configuration.get("language_roles") or {},
            "message_id": configuration.get("message_id"),
            "role_name_mask": configuration.get("role_name_mask") or "{group} - {name}",
        })
        return legacy
    return _default_groups()


def _role_names(mask: str, languages: list[dict], group_name: str) -> dict[str, str]:
    allowed = {"flag", "name", "code", "group"}
    fields = re.findall(r"\{([^{}]+)\}", mask)
    remaining = re.sub(r"\{(?:flag|name|code|group)\}", "", mask)
    if any(field not in allowed for field in fields) or "{" in remaining or "}" in remaining:
        raise HTTPException(422, "Use only {group}, {flag}, {name} and {code} in the role mask")
    names = {item["code"]: mask.format(**item, group=group_name).strip() for item in languages}
    if any(not name or len(name) > 100 or name == "@everyone" for name in names.values()):
        raise HTTPException(422, "Generated role names must contain 1-100 characters")
    if len({name.casefold() for name in names.values()}) != len(names):
        raise HTTPException(422, "The role mask must produce distinct names")
    return names


async def _installation(session: AsyncSession, guild_id: int) -> GuildPluginInstallation | None:
    return await session.scalar(select(GuildPluginInstallation).where(
        GuildPluginInstallation.guild_id == guild_id,
        GuildPluginInstallation.plugin_key == "first_introduction",
    ))


async def _languages(session: AsyncSession, guild_id: int) -> list[dict]:
    rows = (await session.execute(
        select(GlobalLanguage.code, GlobalLanguage.native_name, GlobalLanguage.flag)
        .join(GuildLanguage, GuildLanguage.language_code == GlobalLanguage.code)
        .where(GuildLanguage.guild_id == guild_id, GuildLanguage.enabled.is_(True),
               GlobalLanguage.is_active.is_(True))
        .order_by(GuildLanguage.sort_order, GlobalLanguage.name)
    )).all()
    return [{"code": code, "name": name, "flag": flag} for code, name, flag in rows]


async def _settings(session: AsyncSession, guild_id: int) -> dict:
    installation = await _installation(session, guild_id)
    config = (installation.configuration or {}) if installation else {}
    return {"installed": installation is not None,
            "enabled": bool(installation and installation.enabled),
            "languages": await _languages(session, guild_id),
            "groups": _groups(config)}


@router.get("/discord/guilds/{guild_id}/plugins/first-introduction/settings")
async def get_settings(guild_id: int, user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    return await _settings(session, guild_id)


@router.put("/discord/guilds/{guild_id}/plugins/first-introduction/settings")
async def save_settings(guild_id: int, payload: SettingsInput,
                        user: User = Depends(get_current_user),
                        session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    installation = await _installation(session, guild_id)
    if installation is None:
        raise HTTPException(409, "Install Language Selection before configuring it")
    languages = await _languages(session, guild_id)
    if not 1 <= len(languages) <= 25:
        raise HTTPException(422, "Configure 1-25 server languages first")
    codes = {item["code"] for item in languages}
    flags = [item["flag"] for item in languages]
    if any(not flag for flag in flags) or len(set(flags)) != len(flags):
        raise HTTPException(422, "Each server language needs a unique flag")
    previous = {group["id"]: group for group in _groups(installation.configuration or {})}
    saved = []
    for group in payload.groups:
        _role_names(group.role_name_mask, languages, group.name)
        if set(group.language_roles) - codes:
            raise HTTPException(422, f"Unknown language role in {group.name}")
        if installation.enabled and group.enabled and (not group.channel_id or not group.access_role_id or
                              set(group.language_roles) != codes):
            raise HTTPException(422, f"{group.name}: select a channel, access role and every language role")
        data = group.model_dump()
        old = previous.get(group.id) or {}
        data["message_id"] = (old.get("message_id") if
                              old.get("channel_id") == group.channel_id and
                              old.get("language_roles") == group.language_roles else None)
        saved.append(data)
    installation.configuration = {**(installation.configuration or {}), "groups": saved}
    await session.commit()
    return await _settings(session, guild_id)


@router.post("/discord/guilds/{guild_id}/plugins/first-introduction/roles/ensure")
async def ensure_language_roles(guild_id: int, payload: RoleProvisionInput,
                                user: User = Depends(get_current_user),
                                session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    installation = await session.scalar(select(GuildPluginInstallation).where(
        GuildPluginInstallation.guild_id == guild_id,
        GuildPluginInstallation.plugin_key == "first_introduction").with_for_update())
    if installation is None:
        raise HTTPException(409, "Install Language Selection first")
    groups = _groups(installation.configuration or {})
    group = next((item for item in groups if item["id"] == payload.group_id), None)
    if group is None:
        raise HTTPException(404, "Language group not found. Save the group first")
    languages = await _languages(session, guild_id)
    if not 1 <= len(languages) <= 25:
        raise HTTPException(422, "Configure 1-25 server languages first")
    names = _role_names(payload.role_name_mask, languages, group["name"])
    roles = (await session.execute(select(DiscordGuildRole).where(
        DiscordGuildRole.guild_id == guild_id))).scalars().all()
    by_id = {str(role.discord_role_id): role for role in roles}
    by_name = {role.name.casefold(): role for role in roles if not role.managed and role.assignable}
    other_group_roles = {role_id for item in groups if item["id"] != group["id"]
                         for role_id in (item.get("language_roles") or {}).values()}
    assigned = dict(group.get("language_roles") or {})
    queued = []
    existing_jobs = (await session.execute(select(DiscordStructureChange).where(
        DiscordStructureChange.guild_id == guild_id,
        DiscordStructureChange.object_type == "role",
        DiscordStructureChange.operation == "create",
        DiscordStructureChange.status.in_(["pending", "processing"])))).scalars().all()
    for code, name in names.items():
        current = by_id.get(str(assigned.get(code) or ""))
        if current and not current.managed and current.assignable:
            continue
        assigned.pop(code, None)
        matching = by_name.get(name.casefold())
        if matching and str(matching.discord_role_id) not in other_group_roles:
            assigned[code] = str(matching.discord_role_id)
            continue
        pending = next((job for job in existing_jobs if
            (job.payload or {}).get("_plugin") == "first_introduction" and
            (job.payload or {}).get("_group_id", "r1") == group["id"] and
            (job.payload or {}).get("language_code") == code), None)
        if pending:
            queued.append(str(pending.id))
            continue
        job = DiscordStructureChange(guild_id=guild_id, object_type="role", operation="create",
            payload={"name": name, "permissions": "0", "reuse_existing": True,
                     "_plugin": "first_introduction", "_group_id": group["id"],
                     "language_code": code},
            preview={"safe_to_apply": True}, status="pending", requested_by=user.id)
        session.add(job)
        await session.flush()
        queued.append(str(job.id))
    group["language_roles"] = assigned
    group["role_name_mask"] = payload.role_name_mask
    installation.configuration = {**(installation.configuration or {}), "groups": groups}
    await session.commit()
    return {"jobs": queued, "language_roles": assigned, "role_names": names}


@router.post("/discord/guilds/{guild_id}/plugins/first-introduction/roles/status")
async def language_role_jobs(guild_id: int, job_ids: list[UUID],
                             user: User = Depends(get_current_user),
                             session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    if len(job_ids) > 25:
        raise HTTPException(422, "Too many role jobs")
    jobs = (await session.execute(select(DiscordStructureChange).where(
        DiscordStructureChange.guild_id == guild_id,
        DiscordStructureChange.id.in_(job_ids)))).scalars().all()
    if len(jobs) != len(set(job_ids)) or any((job.payload or {}).get("_plugin") != "first_introduction" for job in jobs):
        raise HTTPException(404, "Language role job not found")
    return {"complete": all(job.status in {"completed", "failed"} for job in jobs),
            "items": [{"id": str(job.id), "group_id": job.payload.get("_group_id", "r1"),
                       "language_code": job.payload.get("language_code"),
                       "name": job.payload.get("name"), "status": job.status,
                       "role_id": str((job.payload.get("_result") or {}).get("role_id") or ""),
                       "error": job.result_message} for job in jobs]}


@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_config(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    return await _settings(session, guild_id)


@internal_router.post("/panel")
async def internal_panel(payload: PanelInput, session: AsyncSession = Depends(get_db_session)):
    installation = await _installation(session, payload.guild_id)
    if not installation or not installation.enabled:
        raise HTTPException(409, "Language Selection is disabled")
    groups = _groups(installation.configuration or {})
    group = next((item for item in groups if item["id"] == payload.group_id and item.get("enabled")), None)
    if group is None or group.get("channel_id") != payload.channel_id:
        raise HTTPException(422, "Panel group or channel does not match configuration")
    group["message_id"] = payload.message_id
    installation.configuration = {**(installation.configuration or {}), "groups": groups}
    await session.commit()
    return {"group_id": group["id"], "message_id": payload.message_id}
