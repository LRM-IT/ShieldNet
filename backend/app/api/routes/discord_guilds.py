from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import User
from app.models.discord import Guild, GuildMembership, MembershipStatus
from app.schemas.discord import GuildAccessResponse
from app.services.global_access import GlobalAccessService

router = APIRouter(prefix="/discord", tags=["Discord"])


@router.get("/guilds", response_model=list[GuildAccessResponse])
async def list_my_guilds(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    if GlobalAccessService.is_superadmin(current_user):
        guilds = (await session.execute(select(Guild).order_by(Guild.name))).scalars().all()
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
            or_(GuildMembership.expires_at.is_(None), GuildMembership.expires_at > datetime.now(UTC)),
        )
        .order_by(Guild.name)
    )
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
        )
        for g, m in result.all()
    ]
