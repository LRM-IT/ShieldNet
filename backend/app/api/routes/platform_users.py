from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.core import User
from app.models.discord import Guild
from app.models.member_actions import MemberActionType
from app.schemas.member_actions import MemberActionCreate
from app.services.member_action_service import MemberActionService


router = APIRouter(prefix="/platform/users", tags=["Platform Users"])


class DirectMessagePayload(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


def serialize_user(user: User, guilds: list[Guild]) -> dict:
    return {
        "id": str(user.id),
        "display_name": user.display_name,
        "login": user.login,
        "email": user.email,
        "email_verified": user.email_verified,
        "avatar_url": user.avatar_url,
        "discord_user_id": str(user.discord_user_id) if user.discord_user_id else None,
        "status": user.status.value,
        "preferred_locale": user.preferred_locale,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "guilds": [
            {
                "guild_id": str(guild.guild_id),
                "name": guild.name,
                "icon_url": guild.icon_url,
                "status": guild.status.value,
                "bot_status": guild.bot_status.value,
            }
            for guild in guilds
        ],
    }


@router.get("")
async def list_server_owners(
    search: str = Query("", max_length=120),
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
):
    guilds = (await session.execute(select(Guild).order_by(Guild.name))).scalars().all()
    owner_ids = {guild.owner_discord_id for guild in guilds}
    if not owner_ids:
        return {"items": [], "total": 0}

    statement = select(User).where(User.discord_user_id.in_(owner_ids), User.deleted_at.is_(None))
    term = search.strip()
    if term:
        pattern = f"%{term}%"
        filters = [User.email.ilike(pattern), User.login.ilike(pattern), User.display_name.ilike(pattern)]
        if term.isdigit():
            filters.append(User.discord_user_id == int(term))
        statement = statement.where(or_(*filters))
    users = (await session.execute(statement.order_by(User.display_name, User.login))).scalars().all()
    by_owner: dict[int, list[Guild]] = {}
    for guild in guilds:
        by_owner.setdefault(guild.owner_discord_id, []).append(guild)
    items = [serialize_user(user, by_owner.get(user.discord_user_id or 0, [])) for user in users]
    return {"items": items, "total": len(items)}


@router.get("/{user_id}")
async def get_server_owner(
    user_id: UUID,
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
):
    owner = await session.get(User, user_id)
    if owner is None or owner.deleted_at is not None or owner.discord_user_id is None:
        raise HTTPException(status_code=404, detail="Server owner not found")
    guilds = (
        await session.execute(
            select(Guild).where(Guild.owner_discord_id == owner.discord_user_id).order_by(Guild.name)
        )
    ).scalars().all()
    if not guilds:
        raise HTTPException(status_code=404, detail="Server owner not found")
    return serialize_user(owner, guilds)


@router.post("/{user_id}/dm", status_code=status.HTTP_202_ACCEPTED)
async def send_owner_dm(
    user_id: UUID,
    payload: DirectMessagePayload,
    current_user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    owner = await session.get(User, user_id)
    if owner is None or owner.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found")
    if owner.discord_user_id is None:
        raise HTTPException(status_code=409, detail="This user has no linked Discord account")

    guild = (
        await session.execute(
            select(Guild)
            .where(Guild.owner_discord_id == owner.discord_user_id)
            .order_by(Guild.bot_status.desc(), Guild.name)
            .limit(1)
        )
    ).scalar_one_or_none()
    if guild is None:
        raise HTTPException(status_code=409, detail="This user does not own a registered server")

    action = await MemberActionService(session).create(
        guild_id=guild.guild_id,
        discord_user_id=owner.discord_user_id,
        requested_by=current_user.id,
        data=MemberActionCreate(
            action_type=MemberActionType.SEND_DM,
            payload={"message": message, "source": "platform_superadmin"},
        ),
    )
    return {"id": str(action.id), "status": action.status.value, "guild_id": str(guild.guild_id)}
