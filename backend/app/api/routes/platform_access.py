from datetime import UTC, datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.platform_access import require_platform_viewer
from app.db.session import get_db_session
from app.models.core import PlatformDiscordAdmin, Session, User
from app.models.discord import Guild, GuildMembership, MembershipStatus
from app.services.global_access import GlobalAccessService

router = APIRouter(prefix="/platform/access", tags=["Platform Access"])
ALLOWED_ROLES = {"platform_admin", "platform_operator", "platform_auditor"}


class DiscordAdminCreate(BaseModel):
    discord_user_id: str
    role: str = Field(default="platform_admin")
    display_name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    expires_at: datetime | None = None

    @field_validator("discord_user_id")
    @classmethod
    def validate_discord_id(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or not (15 <= len(value) <= 22):
            raise ValueError("Discord User ID must contain 15-22 digits")
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in ALLOWED_ROLES:
            raise ValueError("Unsupported platform role")
        return value


class DiscordAdminUpdate(BaseModel):
    role: str | None = None
    display_name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    expires_at: datetime | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str | None) -> str | None:
        if value is not None and value not in ALLOWED_ROLES:
            raise ValueError("Unsupported platform role")
        return value


def require_local_owner(user: User) -> None:
    GlobalAccessService.require_superadmin(user)
    if getattr(user, "_auth_source", None) != "local_platform":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local platform authentication required",
        )


def serialize(item: PlatformDiscordAdmin) -> dict:
    return {
        "id": str(item.id),
        "discord_user_id": str(item.discord_user_id),
        "role": item.role,
        "display_name": item.display_name,
        "description": item.description,
        "is_active": item.is_active,
        "expires_at": item.expires_at,
        "last_login_at": item.last_login_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/me")
async def platform_access_me(current_user: User = Depends(get_current_user)) -> dict:
    auth_source = getattr(current_user, "_auth_source", "discord_guild")
    platform_role = getattr(current_user, "_platform_role", None)
    return {
        "user_id": str(current_user.id),
        "discord_user_id": str(current_user.discord_user_id) if current_user.discord_user_id else None,
        "roles": GlobalAccessService.effective_role_names(current_user),
        "highest_role": GlobalAccessService.highest_role(current_user).value if GlobalAccessService.highest_role(current_user) else None,
        "is_superadmin": GlobalAccessService.is_superadmin(current_user),
        "auth_source": auth_source,
        "platform_role": platform_role,
        "has_platform_access": auth_source in {"local_platform", "discord_platform"},
        "can_manage_platform_admins": auth_source == "local_platform" and GlobalAccessService.is_superadmin(current_user),
    }


@router.get("/overview")
async def platform_access_overview(
    _: User = Depends(require_platform_viewer),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    now = datetime.now(UTC)
    return {
        "guild_count": await session.scalar(select(func.count()).select_from(Guild)) or 0,
        "active_memberships": await session.scalar(
            select(func.count()).select_from(GuildMembership).where(GuildMembership.status == MembershipStatus.ACTIVE)
        ) or 0,
        "user_count": await session.scalar(select(func.count()).select_from(User)) or 0,
        "configured_superadmins": await session.scalar(
            select(func.count()).select_from(PlatformDiscordAdmin).where(
                PlatformDiscordAdmin.is_active.is_(True),
                (PlatformDiscordAdmin.expires_at.is_(None) | (PlatformDiscordAdmin.expires_at > now)),
            )
        ) or 0,
        "configuration_key": "database",
    }


@router.get("/discord-admins")
async def list_discord_admins(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    require_local_owner(current_user)
    rows = (
        await session.execute(select(PlatformDiscordAdmin).order_by(PlatformDiscordAdmin.created_at.desc()))
    ).scalars().all()
    return [serialize(row) for row in rows]


@router.post("/discord-admins", status_code=status.HTTP_201_CREATED)
async def create_discord_admin(
    payload: DiscordAdminCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    require_local_owner(current_user)
    discord_user_id = int(payload.discord_user_id)
    existing = await session.scalar(
        select(PlatformDiscordAdmin).where(PlatformDiscordAdmin.discord_user_id == discord_user_id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Discord administrator already exists")
    item = PlatformDiscordAdmin(
        discord_user_id=discord_user_id,
        role=payload.role,
        display_name=payload.display_name,
        description=payload.description,
        expires_at=payload.expires_at,
        created_by_user_id=current_user.id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return serialize(item)


@router.patch("/discord-admins/{admin_id}")
async def update_discord_admin(
    admin_id: uuid.UUID,
    payload: DiscordAdminUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    require_local_owner(current_user)
    item = await session.get(PlatformDiscordAdmin, admin_id)
    if not item:
        raise HTTPException(status_code=404, detail="Discord administrator not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return serialize(item)


@router.post("/discord-admins/{admin_id}/revoke-sessions", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_discord_admin_sessions(
    admin_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    require_local_owner(current_user)
    item = await session.get(PlatformDiscordAdmin, admin_id)
    if not item:
        raise HTTPException(status_code=404, detail="Discord administrator not found")
    user = await session.scalar(select(User).where(User.discord_user_id == item.discord_user_id))
    if user:
        await session.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/discord-admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_discord_admin(
    admin_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    require_local_owner(current_user)
    item = await session.get(PlatformDiscordAdmin, admin_id)
    if not item:
        raise HTTPException(status_code=404, detail="Discord administrator not found")
    user = await session.scalar(select(User).where(User.discord_user_id == item.discord_user_id))
    if user:
        await session.execute(
            update(Session)
            .where(Session.user_id == user.id, Session.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
