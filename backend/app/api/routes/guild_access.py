from datetime import UTC, datetime, timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.audit import AuditEvent
from app.models.core import Session, User
from app.models.discord import Guild, GuildMembership, MembershipRole, MembershipStatus
from app.services.global_access import GlobalAccessService

router = APIRouter(prefix="/guilds/{guild_id}/access", tags=["Guild Access"])

ALLOWED_PERMISSIONS = {
    "members",
    "verification",
    "moderation",
    "security",
    "plugins",
    "automations",
    "audit",
    "settings",
    "access",
}


class GuildAccessCreate(BaseModel):
    discord_user_id: str
    role: MembershipRole = MembershipRole.MODERATOR
    permissions: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None

    @field_validator("discord_user_id")
    @classmethod
    def validate_discord_id(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or not 15 <= len(value) <= 22:
            raise ValueError("Discord User ID must contain 15-22 digits")
        return value

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, values: list[str]) -> list[str]:
        unknown = sorted(set(values) - ALLOWED_PERMISSIONS)
        if unknown:
            raise ValueError(f"Unsupported permissions: {', '.join(unknown)}")
        return sorted(set(values))


class GuildAccessUpdate(BaseModel):
    role: MembershipRole | None = None
    permissions: list[str] | None = None
    status: MembershipStatus | None = None
    expires_at: datetime | None = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        unknown = sorted(set(values) - ALLOWED_PERMISSIONS)
        if unknown:
            raise ValueError(f"Unsupported permissions: {', '.join(unknown)}")
        return sorted(set(values))


def serialize(item: GuildMembership, owner_discord_id: int) -> dict:
    now = datetime.now(UTC)
    expires_at = item.expires_at
    seconds_remaining = None
    if expires_at is not None:
        seconds_remaining = max(0, int((expires_at - now).total_seconds()))
    return {
        "id": str(item.id),
        "guild_id": str(item.guild_id),
        "discord_user_id": str(item.discord_user_id),
        "role": item.role.value,
        "status": item.status.value,
        "permissions": sorted((item.permissions or {}).get("modules", [])),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "is_expired": bool(expires_at and expires_at <= now),
        "expires_soon": bool(expires_at and now < expires_at <= now + timedelta(days=7)),
        "seconds_remaining": seconds_remaining,
        "is_guild_owner": item.discord_user_id == owner_discord_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def serialize_audit_event(item: AuditEvent) -> dict:
    return {
        "id": str(item.id),
        "event_type": item.event_type,
        "actor_user_id": str(item.actor_user_id) if item.actor_user_id else None,
        "target_type": item.target_type,
        "target_id": item.target_id,
        "payload": item.payload or {},
        "result": item.result,
        "message": item.message,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


async def require_access_owner(session: AsyncSession, user: User, guild_id: int) -> Guild:
    guild = await session.get(Guild, guild_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="Guild not found")
    if GlobalAccessService.is_superadmin(user):
        return guild
    if user.discord_user_id is not None and guild.owner_discord_id == user.discord_user_id:
        return guild
    result = await session.execute(
        select(GuildMembership).where(
            GuildMembership.guild_id == guild_id,
            or_(GuildMembership.user_id == user.id, GuildMembership.discord_user_id == user.discord_user_id),
            GuildMembership.status == MembershipStatus.ACTIVE,
            GuildMembership.role == MembershipRole.ADMIN,
        )
    )
    membership = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if (
        membership
        and (membership.expires_at is None or membership.expires_at > now)
        and "access" in ((membership.permissions or {}).get("modules", []))
    ):
        return guild
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the guild owner or delegated access administrator may manage guild access",
    )


async def audit(
    session: AsyncSession,
    guild_id: int,
    actor: User,
    event_type: str,
    target_id: str,
    payload: dict,
) -> None:
    session.add(
        AuditEvent(
            guild_id=guild_id,
            actor_user_id=actor.id,
            event_type=event_type,
            target_type="guild_membership",
            target_id=target_id,
            payload=payload,
            result="success",
        )
    )


async def expire_memberships(
    session: AsyncSession,
    guild_id: int,
    owner_discord_id: int,
) -> int:
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(GuildMembership).where(
                GuildMembership.guild_id == guild_id,
                GuildMembership.status == MembershipStatus.ACTIVE,
                GuildMembership.expires_at.is_not(None),
                GuildMembership.expires_at <= now,
                GuildMembership.discord_user_id != owner_discord_id,
            )
        )
    ).scalars().all()

    for item in rows:
        item.status = MembershipStatus.REVOKED

        if item.user_id:
            await session.execute(
                update(Session)
                .where(
                    Session.user_id == item.user_id,
                    Session.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )

        session.add(
            AuditEvent(
                guild_id=guild_id,
                actor_user_id=None,
                event_type="guild_access.expired",
                target_type="guild_membership",
                target_id=str(item.id),
                payload={
                    "discord_user_id": str(item.discord_user_id),
                    "expires_at": item.expires_at.isoformat(),
                },
                result="success",
                message="Delegated guild access expired automatically",
            )
        )

    if rows:
        await session.commit()

    return len(rows)


@router.get("")
async def list_access(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    guild = await require_access_owner(session, current_user, guild_id)
    expired_count = await expire_memberships(
        session,
        guild_id,
        guild.owner_discord_id,
    )

    rows = (
        await session.execute(
            select(GuildMembership)
            .where(GuildMembership.guild_id == guild_id)
            .order_by(GuildMembership.created_at)
        )
    ).scalars().all()

    serialized = [serialize(item, guild.owner_discord_id) for item in rows]

    return {
        "guild_id": str(guild_id),
        "owner_discord_id": str(guild.owner_discord_id),
        "allowed_permissions": sorted(ALLOWED_PERMISSIONS),
        "expired_now": expired_count,
        "expires_soon_count": sum(
            1
            for item in serialized
            if item["expires_soon"]
            and item["status"] == MembershipStatus.ACTIVE.value
        ),
        "items": serialized,
    }


@router.get("/history")
async def access_history(
    guild_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await require_access_owner(session, current_user, guild_id)

    rows = (
        await session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.guild_id == guild_id,
                AuditEvent.event_type.like("guild_access.%"),
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    return {
        "guild_id": str(guild_id),
        "items": [serialize_audit_event(item) for item in rows],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_access(
    guild_id: int,
    payload: GuildAccessCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    guild = await require_access_owner(session, current_user, guild_id)
    discord_user_id = int(payload.discord_user_id)

    if discord_user_id == guild.owner_discord_id:
        raise HTTPException(
            status_code=409,
            detail="The guild owner already has permanent full access",
        )

    existing = (
        await session.execute(
            select(GuildMembership).where(
                GuildMembership.guild_id == guild_id,
                GuildMembership.discord_user_id == discord_user_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Guild access already exists for this Discord user",
        )

    item = GuildMembership(
        guild_id=guild_id,
        discord_user_id=discord_user_id,
        role=payload.role,
        status=MembershipStatus.ACTIVE,
        permissions={"modules": payload.permissions},
        expires_at=payload.expires_at,
        created_by=current_user.id,
    )

    session.add(item)
    await session.flush()

    await audit(
        session,
        guild_id,
        current_user,
        "guild_access.created",
        str(item.id),
        serialize(item, guild.owner_discord_id),
    )

    await session.commit()
    await session.refresh(item)
    return serialize(item, guild.owner_discord_id)


@router.patch("/{membership_id}")
async def update_access(
    guild_id: int,
    membership_id: uuid.UUID,
    payload: GuildAccessUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    guild = await require_access_owner(session, current_user, guild_id)
    item = await session.get(GuildMembership, membership_id)

    if item is None or item.guild_id != guild_id:
        raise HTTPException(
            status_code=404,
            detail="Guild access entry not found",
        )

    if item.discord_user_id == guild.owner_discord_id:
        raise HTTPException(
            status_code=409,
            detail="The guild owner access cannot be changed",
        )

    changes = payload.model_dump(exclude_unset=True)

    if "permissions" in changes:
        item.permissions = {"modules": changes.pop("permissions")}

    for key, value in changes.items():
        setattr(item, key, value)

    await audit(
        session,
        guild_id,
        current_user,
        "guild_access.updated",
        str(item.id),
        serialize(item, guild.owner_discord_id),
    )

    await session.commit()
    await session.refresh(item)
    return serialize(item, guild.owner_discord_id)


@router.post("/{membership_id}/revoke-sessions", status_code=204)
async def revoke_access_sessions(
    guild_id: int,
    membership_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    guild = await require_access_owner(session, current_user, guild_id)
    item = await session.get(GuildMembership, membership_id)

    if item is None or item.guild_id != guild_id:
        raise HTTPException(
            status_code=404,
            detail="Guild access entry not found",
        )

    if item.discord_user_id == guild.owner_discord_id:
        raise HTTPException(
            status_code=409,
            detail="The guild owner sessions cannot be revoked here",
        )

    if item.user_id:
        await session.execute(
            update(Session)
            .where(
                Session.user_id == item.user_id,
                Session.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )

    await audit(
        session,
        guild_id,
        current_user,
        "guild_access.sessions_revoked",
        str(item.id),
        {},
    )

    await session.commit()
    return Response(status_code=204)


@router.delete("/{membership_id}", status_code=204)
async def delete_access(
    guild_id: int,
    membership_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    guild = await require_access_owner(session, current_user, guild_id)
    item = await session.get(GuildMembership, membership_id)

    if item is None or item.guild_id != guild_id:
        raise HTTPException(
            status_code=404,
            detail="Guild access entry not found",
        )

    if item.discord_user_id == guild.owner_discord_id:
        raise HTTPException(
            status_code=409,
            detail="The guild owner access cannot be removed",
        )

    if item.user_id:
        await session.execute(
            update(Session)
            .where(
                Session.user_id == item.user_id,
                Session.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )

    target_id = str(item.id)
    discord_user_id = str(item.discord_user_id)

    await session.delete(item)

    await audit(
        session,
        guild_id,
        current_user,
        "guild_access.deleted",
        target_id,
        {"discord_user_id": discord_user_id},
    )

    await session.commit()
    return Response(status_code=204)
