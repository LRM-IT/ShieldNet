from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.global_languages import GlobalLanguage
from app.models.guild_languages import GuildLanguage
from app.models.plugins import GuildPluginInstallation
from app.models.guild_roles import DiscordGuildRole
from app.models.role_channel_management import DiscordStructureChange

router = APIRouter(tags=["Language Selection plugin"])
internal_router = APIRouter(
    prefix="/internal/plugin-first-introduction",
    tags=["Internal Language Selection plugin"],
    dependencies=[Depends(verify_internal_service_token)],
)


class SettingsInput(BaseModel):
    language_roles: dict[str, str] = Field(default_factory=dict)
    channel_id: str | None = None
    role_name_mask: str = Field(default="{flag} {name}", min_length=1, max_length=100)

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


class RoleProvisionInput(BaseModel):
    role_name_mask: str = Field(min_length=1, max_length=100)


def _role_names(mask: str, languages: list[dict]) -> dict[str, str]:
    import re
    allowed = {"flag", "name", "code"}
    fields = re.findall(r"\{([^{}]+)\}", mask)
    if any(field not in allowed for field in fields) or "{" in re.sub(r"\{(?:flag|name|code)\}", "", mask) or "}" in re.sub(r"\{(?:flag|name|code)\}", "", mask):
        raise HTTPException(422, "Use only {flag}, {name} and {code} in the role name mask")
    names = {item["code"]: mask.format(**item).strip() for item in languages}
    if any(not name or len(name) > 100 or name == "@everyone" for name in names.values()):
        raise HTTPException(422, "Generated role names must contain 1-100 characters")
    if len({name.casefold() for name in names.values()}) != len(names):
        raise HTTPException(422, "The role name mask must produce unique names")
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
        "role_name_mask": configuration.get("role_name_mask") or "{flag} {name}",
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
    _role_names(payload.role_name_mask, configured)
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


@router.post("/discord/guilds/{guild_id}/plugins/first-introduction/roles/ensure")
async def ensure_language_roles(guild_id: int, payload: RoleProvisionInput,
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    installation = await session.scalar(select(GuildPluginInstallation).where(
        GuildPluginInstallation.guild_id == guild_id,
        GuildPluginInstallation.plugin_key == "first_introduction").with_for_update())
    if installation is None:
        raise HTTPException(409, "Install Language Selection first")
    languages = await _languages(session, guild_id)
    if not languages or len(languages) > 25:
        raise HTTPException(422, "Configure 1-25 server languages first")
    names = _role_names(payload.role_name_mask, languages)
    roles = (await session.execute(select(DiscordGuildRole).where(
        DiscordGuildRole.guild_id == guild_id))).scalars().all()
    by_id = {str(role.discord_role_id): role for role in roles}
    by_name = {role.name.casefold(): role for role in roles if not role.managed and role.assignable}
    config = dict(installation.configuration or {})
    assigned = dict(config.get("language_roles") or {})
    batch_id = uuid4()
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
        if matching:
            assigned[code] = str(matching.discord_role_id)
            continue
        pending = next((job for job in existing_jobs if
            (job.payload or {}).get("_plugin") == "first_introduction" and
            (job.payload or {}).get("language_code") == code), None)
        if pending:
            queued.append(str(pending.id))
            continue
        job = DiscordStructureChange(guild_id=guild_id, object_type="role", operation="create",
            payload={"name": name, "permissions": "0", "reuse_existing": True,
                     "_plugin": "first_introduction", "language_code": code,
                     "batch_id": str(batch_id)},
            preview={"safe_to_apply": True}, status="pending", requested_by=user.id)
        session.add(job)
        await session.flush()
        queued.append(str(job.id))
    config["language_roles"] = assigned
    config["role_name_mask"] = payload.role_name_mask
    installation.configuration = config
    await session.commit()
    return {"batch_id": str(batch_id), "jobs": queued, "language_roles": assigned,
            "role_names": names}


@router.post("/discord/guilds/{guild_id}/plugins/first-introduction/roles/status")
async def language_role_jobs(guild_id: int, job_ids: list[UUID],
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    if len(job_ids) > 25:
        raise HTTPException(422, "Too many role jobs")
    jobs = (await session.execute(select(DiscordStructureChange).where(
        DiscordStructureChange.guild_id == guild_id,
        DiscordStructureChange.id.in_(job_ids)))).scalars().all()
    if len(jobs) != len(set(job_ids)) or any((job.payload or {}).get("_plugin") != "first_introduction" for job in jobs):
        raise HTTPException(404, "Language role job not found")
    return {"complete": all(job.status in {"completed", "failed"} for job in jobs),
            "items": [{"id": str(job.id), "language_code": job.payload.get("language_code"),
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
    configuration = installation.configuration or {}
    if configuration.get("channel_id") != payload.channel_id:
        raise HTTPException(422, "Panel channel does not match configuration")
    installation.configuration = {**configuration, "message_id": payload.message_id}
    await session.commit()
    return {"message_id": payload.message_id}
