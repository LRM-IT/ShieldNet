from datetime import UTC, datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.core import PlatformDiscordAdmin, User
from app.models.discord import Guild, GuildMembership, MembershipStatus
from app.services.global_access import GlobalAccessService

router = APIRouter(prefix="/platform/access", tags=["Platform Access"])

class DiscordAdminCreate(BaseModel):
    discord_user_id: int
    role: str = Field(default="platform_admin", pattern="^(platform_admin|platform_operator|platform_auditor)$")
    display_name: str | None = None
    description: str | None = None
    expires_at: datetime | None = None

class DiscordAdminUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(platform_admin|platform_operator|platform_auditor)$")
    display_name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    expires_at: datetime | None = None

def require_local_owner(user: User) -> None:
    GlobalAccessService.require_superadmin(user)
    if getattr(user, "_auth_source", None) != "local_platform":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local platform authentication required")

def serialize(item: PlatformDiscordAdmin) -> dict:
    return {"id": str(item.id), "discord_user_id": str(item.discord_user_id), "role": item.role, "display_name": item.display_name, "description": item.description, "is_active": item.is_active, "expires_at": item.expires_at, "last_login_at": item.last_login_at, "created_at": item.created_at}

@router.get("/me")
async def platform_access_me(current_user: User = Depends(get_current_user)) -> dict:
    return {"user_id": str(current_user.id), "discord_user_id": current_user.discord_user_id, "roles": GlobalAccessService.effective_role_names(current_user), "highest_role": GlobalAccessService.highest_role(current_user).value if GlobalAccessService.highest_role(current_user) else None, "is_superadmin": GlobalAccessService.is_superadmin(current_user), "auth_source": getattr(current_user, "_auth_source", "discord_guild"), "can_manage_platform_admins": getattr(current_user, "_auth_source", None) == "local_platform" and GlobalAccessService.is_superadmin(current_user)}

@router.get("/overview")
async def platform_access_overview(_: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)) -> dict:
    return {"guild_count": await session.scalar(select(func.count()).select_from(Guild)) or 0, "active_memberships": await session.scalar(select(func.count()).select_from(GuildMembership).where(GuildMembership.status == MembershipStatus.ACTIVE)) or 0, "user_count": await session.scalar(select(func.count()).select_from(User)) or 0, "configured_superadmins": await session.scalar(select(func.count()).select_from(PlatformDiscordAdmin).where(PlatformDiscordAdmin.is_active.is_(True))) or 0, "configuration_key": "database"}

@router.get("/discord-admins")
async def list_discord_admins(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> list[dict]:
    require_local_owner(current_user)
    rows = (await session.execute(select(PlatformDiscordAdmin).order_by(PlatformDiscordAdmin.created_at.desc()))).scalars().all()
    return [serialize(row) for row in rows]

@router.post("/discord-admins", status_code=201)
async def create_discord_admin(payload: DiscordAdminCreate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> dict:
    require_local_owner(current_user)
    existing = await session.scalar(select(PlatformDiscordAdmin).where(PlatformDiscordAdmin.discord_user_id == payload.discord_user_id))
    if existing: raise HTTPException(status_code=409, detail="Discord administrator already exists")
    item = PlatformDiscordAdmin(**payload.model_dump(), created_by_user_id=current_user.id)
    session.add(item); await session.commit(); await session.refresh(item); return serialize(item)

@router.patch("/discord-admins/{admin_id}")
async def update_discord_admin(admin_id: uuid.UUID, payload: DiscordAdminUpdate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> dict:
    require_local_owner(current_user)
    item = await session.get(PlatformDiscordAdmin, admin_id)
    if not item: raise HTTPException(status_code=404, detail="Discord administrator not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    await session.commit(); await session.refresh(item); return serialize(item)

@router.delete("/discord-admins/{admin_id}", status_code=204)
async def delete_discord_admin(admin_id: uuid.UUID, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> None:
    require_local_owner(current_user)
    item = await session.get(PlatformDiscordAdmin, admin_id)
    if not item: raise HTTPException(status_code=404, detail="Discord administrator not found")
    await session.delete(item); await session.commit()
