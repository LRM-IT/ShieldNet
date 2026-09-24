from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import User
from app.models.discord import Guild, GuildMembership, GuildStatus, MembershipStatus
from app.models.billing import BillingSubscription
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
        )
        for g, m in rows
    ]
