from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.models.guild_roles import DiscordGuildRole

router = APIRouter(tags=["Guild Roles"])

@router.get("/discord/guilds/{guild_id}/roles")
async def list_roles(
    guild_id: int,
    include_unassignable: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(session, current_user, guild_id)
    query = select(DiscordGuildRole).where(DiscordGuildRole.guild_id == guild_id)
    if not include_unassignable:
        query = query.where(DiscordGuildRole.assignable.is_(True))
    result = await session.execute(query.order_by(DiscordGuildRole.position.desc()))
    return [{
        "discord_role_id": str(r.discord_role_id),
        "name": r.name,
        "position": r.position,
        "color": r.color,
        "permissions": r.permissions,
        "managed": r.managed,
        "assignable": r.assignable,
    } for r in result.scalars().all()]
