from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import User
from app.models.discord import Guild, GuildMembership, MembershipRole, MembershipStatus
from app.services.global_access import GlobalAccessService

GUILD_MODULES = frozenset({
    "members", "verification", "moderation", "security", "plugins",
    "automations", "audit", "settings", "access",
})


def _expired(membership: GuildMembership) -> bool:
    if membership.expires_at is None:
        return False
    expires_at = membership.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


async def require_guild_management(
    session: AsyncSession,
    user: User,
    guild_id: int,
) -> GuildMembership | None:
    """Authorize basic management access to a Discord guild."""
    if GlobalAccessService.is_superadmin(user):
        from app.services.guild_registry import GuildRegistryService
        await GuildRegistryService(session).ensure_management_target(guild_id, user)
        return None

    guild = await session.get(Guild, guild_id)
    if guild is not None and user.discord_user_id is not None and guild.owner_discord_id == user.discord_user_id:
        result = await session.execute(
            select(GuildMembership).where(
                GuildMembership.guild_id == guild_id,
                GuildMembership.discord_user_id == user.discord_user_id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            membership = GuildMembership(
                guild_id=guild_id,
                user_id=user.id,
                discord_user_id=user.discord_user_id,
                role=MembershipRole.ADMIN,
                status=MembershipStatus.ACTIVE,
                permissions=list(GUILD_MODULES),
                created_by=user.id,
            )
            session.add(membership)
        else:
            membership.user_id = user.id
            membership.role = MembershipRole.ADMIN
            membership.status = MembershipStatus.ACTIVE
            membership.permissions = list(GUILD_MODULES)
            membership.expires_at = None
        await session.commit()
        return membership

    identity_filters = [GuildMembership.user_id == user.id]
    if user.discord_user_id is not None:
        identity_filters.append(GuildMembership.discord_user_id == user.discord_user_id)

    result = await session.execute(
        select(GuildMembership).where(
            GuildMembership.guild_id == guild_id,
            or_(*identity_filters),
            GuildMembership.status == MembershipStatus.ACTIVE,
            GuildMembership.role.in_([MembershipRole.ADMIN, MembershipRole.MODERATOR]),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None or _expired(membership):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to manage this server")

    if membership.user_id != user.id:
        membership.user_id = user.id
        await session.commit()
    return membership


async def require_guild_module(
    session: AsyncSession,
    user: User,
    guild_id: int,
    module_key: str,
) -> GuildMembership | None:
    """Require delegated access to one Guild Control Center module."""
    if module_key not in GUILD_MODULES:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unknown guild module permission")

    membership = await require_guild_management(session, user, guild_id)
    if membership is None:  # platform superadmin
        return None

    guild = await session.get(Guild, guild_id)
    if guild is not None and user.discord_user_id == guild.owner_discord_id:
        return membership

    permissions = set(membership.permissions or [])
    if "*" not in permissions and module_key not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "guild_module_forbidden", "module": module_key},
        )
    return membership
