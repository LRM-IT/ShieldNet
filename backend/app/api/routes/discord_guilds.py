from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import User
from app.models.discord import Guild, GuildMembership, GuildStatus, MembershipStatus
from app.models.billing import BillingSubscription
from app.models.modules import GuildModule
from app.schemas.discord import GuildAccessResponse
from app.services.global_access import GlobalAccessService

router = APIRouter(prefix="/discord", tags=["Discord"])

PAID_PACKAGE_KEY = "__paid_modules__"

async def _billing_by_guild(session: AsyncSession, guild_ids: list[int]) -> dict[int, BillingSubscription]:
    if not guild_ids:
        return {}
    rows = (await session.execute(select(BillingSubscription).where(
        BillingSubscription.guild_id.in_(guild_ids),
        BillingSubscription.plugin_key == PAID_PACKAGE_KEY,
    ))).scalars().all()
    return {row.guild_id: row for row in rows}

async def _plugin_counts(session: AsyncSession, guild_ids: list[int]) -> dict[int, int]:
    if not guild_ids:
        return {}
    rows = (await session.execute(
        select(GuildModule.guild_id, func.count(GuildModule.id))
        .where(GuildModule.guild_id.in_(guild_ids), GuildModule.enabled.is_(True))
        .group_by(GuildModule.guild_id)
    )).all()
    return {guild_id: count for guild_id, count in rows}

def _sync_status(guild: Guild) -> str:
    if guild.last_sync_at is None:
        return "never"
    return "stale" if guild.last_sync_at < datetime.now(UTC) - timedelta(minutes=15) else "fresh"


@router.get("/guilds", response_model=list[GuildAccessResponse])
async def list_my_guilds(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    if GlobalAccessService.is_superadmin(current_user):
        membership_exists = select(GuildMembership.id).where(
            GuildMembership.guild_id == Guild.guild_id
        ).exists()
        guilds = (await session.execute(
            select(Guild).where(
                Guild.status != GuildStatus.LEFT,
                or_(Guild.last_sync_at.is_not(None), membership_exists)
            ).order_by(Guild.name)
        )).scalars().all()
        billing = await _billing_by_guild(session, [g.guild_id for g in guilds])
        plugins = await _plugin_counts(session, [g.guild_id for g in guilds])
        return [
            GuildAccessResponse(
                guild_id=str(g.guild_id),
                name=g.name,
                icon_url=g.icon_url,
                owner_discord_id=str(g.owner_discord_id),
                member_count=g.member_count,
                guild_status=g.status.value,
                bot_status=g.bot_status.value,
                access_role="admin",
                permissions=["*"],
                expires_at=None,
                is_owner=(g.owner_discord_id == current_user.discord_user_id),
                billing_status=billing[g.guild_id].status if g.guild_id in billing else "inactive",
                billing_expires_at=billing[g.guild_id].expires_at.isoformat() if g.guild_id in billing else None,
                billing_auto_renew=billing[g.guild_id].auto_renew if g.guild_id in billing else False,
                last_sync_at=g.last_sync_at.isoformat() if g.last_sync_at else None,
                sync_status=_sync_status(g),
                enabled_plugins=plugins.get(g.guild_id, 0),
            )
            for g in guilds
        ]

    result = await session.execute(
        select(Guild, GuildMembership)
        .join(GuildMembership, GuildMembership.guild_id == Guild.guild_id)
        .where(
            or_(
                GuildMembership.user_id == current_user.id,
                GuildMembership.discord_user_id == current_user.discord_user_id,
            ),
            GuildMembership.status == MembershipStatus.ACTIVE,
            Guild.status != GuildStatus.LEFT,
            or_(GuildMembership.expires_at.is_(None), GuildMembership.expires_at > datetime.now(UTC)),
        )
        .order_by(Guild.name)
    )
    rows = result.all()
    billing = await _billing_by_guild(session, [g.guild_id for g, _ in rows])
    plugins = await _plugin_counts(session, [g.guild_id for g, _ in rows])
    return [
        GuildAccessResponse(
            guild_id=str(g.guild_id),
            name=g.name,
            icon_url=g.icon_url,
            owner_discord_id=str(g.owner_discord_id),
            member_count=g.member_count,
            guild_status=g.status.value,
            bot_status=g.bot_status.value,
            access_role=m.role.value,
            permissions=(m.permissions or []),
            expires_at=m.expires_at.isoformat() if m.expires_at else None,
            is_owner=(g.owner_discord_id == current_user.discord_user_id),
            billing_status=billing[g.guild_id].status if g.guild_id in billing else "inactive",
            billing_expires_at=billing[g.guild_id].expires_at.isoformat() if g.guild_id in billing else None,
            billing_auto_renew=billing[g.guild_id].auto_renew if g.guild_id in billing else False,
            last_sync_at=g.last_sync_at.isoformat() if g.last_sync_at else None,
            sync_status=_sync_status(g),
            enabled_plugins=plugins.get(g.guild_id, 0),
        )
        for g, m in rows
    ]

@router.delete("/guilds/{guild_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_removed_guild(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    guild = await session.get(Guild, guild_id)
    if guild is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    is_superadmin = GlobalAccessService.is_superadmin(current_user)
    is_owner = bool(current_user.discord_user_id and guild.owner_discord_id == current_user.discord_user_id)
    if not (is_superadmin or is_owner):
        raise HTTPException(status_code=403, detail="Only the server owner can delete this record")
    if guild.bot_status.value == "online":
        raise HTTPException(status_code=409, detail="Disconnect the bot from Discord before deleting this server")
    await session.delete(guild)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
