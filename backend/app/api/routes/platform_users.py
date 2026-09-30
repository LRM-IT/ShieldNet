from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.core import User
from app.models.discord import Guild
from app.models.members import DiscordMember
from app.models.explorer import GuildInvite
from app.models.member_actions import MemberActionType
from app.schemas.member_actions import MemberActionCreate
from app.services.member_action_service import MemberActionService
from app.services.settings import SettingsService


router = APIRouter(prefix="/platform/users", tags=["Platform Users"])


class DirectMessagePayload(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class SupportInviteSettingsPayload(BaseModel):
    enabled: bool = False
    invite_url: str = Field(default="", max_length=500)
    message: str = Field(default="Welcome! Join our Discord support server for help and updates.", max_length=1400)

    @field_validator("invite_url")
    @classmethod
    def validate_invite_url(cls, value: str) -> str:
        value = value.strip()
        if value and not (
            value.startswith("https://discord.gg/")
            or value.startswith("https://discord.com/invite/")
        ):
            raise ValueError("Enter a valid Discord invite URL")
        return value


async def support_invite_settings(session: AsyncSession) -> dict:
    values = await SettingsService(session).list_module(0, "owner_support_invite")
    return {
        "enabled": bool(values.get("enabled", False)),
        "invite_url": str(values.get("invite_url", "")),
        "message": str(values.get("message", "Welcome! Join our Discord support server for help and updates.")),
    }


def serialize_user(user: User | None, guilds: list[Guild], invite_codes: dict[int, str] | None = None, member: DiscordMember | None = None) -> dict:
    invite_codes = invite_codes or {}
    return {
        "id": str(user.id) if user else f"discord:{guilds[0].owner_discord_id}",
        "registered": user is not None,
        "display_name": user.display_name if user else ((member.global_name or member.username) if member else str(guilds[0].owner_discord_id)),
        "login": user.login if user else (member.username if member else ""),
        "email": user.email if user else None,
        "email_verified": user.email_verified if user else False,
        "avatar_url": user.avatar_url if user else (member.avatar_url if member else None),
        "discord_user_id": str(user.discord_user_id if user else guilds[0].owner_discord_id),
        "status": user.status.value if user else "unregistered",
        "preferred_locale": user.preferred_locale if user else None,
        "last_login_at": user.last_login_at if user else None,
        "created_at": user.created_at if user else None,
        "guilds": [
            {
                "guild_id": str(guild.guild_id),
                "name": guild.name,
                "icon_url": guild.icon_url,
                "status": guild.status.value,
                "bot_status": guild.bot_status.value,
                "invite_url": f"https://discord.gg/{invite_codes[guild.guild_id]}" if guild.guild_id in invite_codes else None,
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
    guilds = (
        await session.execute(
            select(Guild).where(Guild.last_sync_at.is_not(None)).order_by(Guild.name)
        )
    ).scalars().all()
    invites = (
        await session.execute(
            select(GuildInvite)
            .where(GuildInvite.guild_id.in_([guild.guild_id for guild in guilds]))
            .order_by(GuildInvite.temporary, GuildInvite.expires_at.nulls_first(), GuildInvite.uses.desc())
        )
    ).scalars().all() if guilds else []
    invite_codes: dict[int, str] = {}
    for invite in invites:
        if invite.max_uses and invite.uses >= invite.max_uses:
            continue
        invite_codes.setdefault(invite.guild_id, invite.code)
    owner_ids = {guild.owner_discord_id for guild in guilds}
    if not owner_ids:
        return {"items": [], "total": 0}

    users = (await session.execute(select(User).where(
        User.discord_user_id.in_(owner_ids), User.deleted_at.is_(None)
    ))).scalars().all()
    users_by_owner = {user.discord_user_id: user for user in users}
    members = (await session.execute(select(DiscordMember).where(
        DiscordMember.discord_user_id.in_(owner_ids),
        DiscordMember.guild_id.in_([guild.guild_id for guild in guilds]),
    ).order_by(DiscordMember.updated_at.desc()))).scalars().all()
    members_by_owner = {}
    for member in members:
        members_by_owner.setdefault(member.discord_user_id, member)
    by_owner: dict[int, list[Guild]] = {}
    for guild in guilds:
        if guild.owner_discord_id > 0:
            by_owner.setdefault(guild.owner_discord_id, []).append(guild)
    items = [serialize_user(users_by_owner.get(owner_id), owned, invite_codes, members_by_owner.get(owner_id))
             for owner_id, owned in by_owner.items()]
    term = search.strip().casefold()
    if term:
        items = [item for item in items if any(term in str(item.get(key) or "").casefold()
                 for key in ("email", "login", "display_name", "discord_user_id"))]
    items.sort(key=lambda item: (item["display_name"] or item["login"] or item["discord_user_id"]).casefold())
    return {"items": items, "total": len(items)}


@router.get("/settings/support-invite")
async def get_support_invite_settings(
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
):
    return await support_invite_settings(session)


@router.put("/settings/support-invite")
async def update_support_invite_settings(
    payload: SupportInviteSettingsPayload,
    current_user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
):
    if payload.enabled and not payload.invite_url:
        raise HTTPException(status_code=422, detail="Discord invite URL is required when the feature is enabled")
    service = SettingsService(session)
    for key, value in payload.model_dump().items():
        await service.set(guild_id=0, module="owner_support_invite", key=key, value=value, updated_by=current_user.id)
    return await support_invite_settings(session)


async def resolve_owner(session: AsyncSession, reference: str) -> tuple[User | None, int]:
    if reference.startswith("discord:"):
        raw_id = reference.removeprefix("discord:")
        if len(raw_id) > 19 or not raw_id.isascii() or not raw_id.isdigit() or not 0 < int(raw_id) < 2**63:
            raise HTTPException(status_code=404, detail="Server owner not found")
        discord_id = int(raw_id)
        user = (await session.execute(select(User).where(
            User.discord_user_id == discord_id, User.deleted_at.is_(None)
        ))).scalar_one_or_none()
        return user, discord_id
    try:
        user_id = UUID(reference)
    except ValueError:
        raise HTTPException(status_code=404, detail="Server owner not found")
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None or user.discord_user_id is None:
        raise HTTPException(status_code=404, detail="Server owner not found")
    return user, user.discord_user_id


@router.get("/{user_id}")
async def get_server_owner(
    user_id: str,
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
):
    owner, discord_id = await resolve_owner(session, user_id)
    guilds = (
        await session.execute(
            select(Guild)
            .where(Guild.owner_discord_id == discord_id, Guild.last_sync_at.is_not(None))
            .order_by(Guild.name)
        )
    ).scalars().all()
    if not guilds:
        raise HTTPException(status_code=404, detail="Server owner not found")
    invites = (
        await session.execute(
            select(GuildInvite)
            .where(GuildInvite.guild_id.in_([guild.guild_id for guild in guilds]))
            .order_by(GuildInvite.temporary, GuildInvite.expires_at.nulls_first(), GuildInvite.uses.desc())
        )
    ).scalars().all()
    invite_codes: dict[int, str] = {}
    for invite in invites:
        if invite.max_uses and invite.uses >= invite.max_uses:
            continue
        invite_codes.setdefault(invite.guild_id, invite.code)
    member = (await session.execute(select(DiscordMember).where(
        DiscordMember.discord_user_id == discord_id,
        DiscordMember.guild_id.in_([guild.guild_id for guild in guilds]),
    ).order_by(DiscordMember.updated_at.desc()).limit(1))).scalar_one_or_none()
    return serialize_user(owner, guilds, invite_codes, member)


@router.post("/{user_id}/dm", status_code=status.HTTP_202_ACCEPTED)
async def send_owner_dm(
    user_id: str,
    payload: DirectMessagePayload,
    current_user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    owner, discord_id = await resolve_owner(session, user_id)

    guild = (
        await session.execute(
            select(Guild)
            .where(Guild.owner_discord_id == discord_id, Guild.last_sync_at.is_not(None))
            .order_by(Guild.bot_status.desc(), Guild.name)
            .limit(1)
        )
    ).scalar_one_or_none()
    if guild is None:
        raise HTTPException(status_code=409, detail="This user does not own a registered server")

    action = await MemberActionService(session).create(
        guild_id=guild.guild_id,
        discord_user_id=discord_id,
        requested_by=current_user.id,
        data=MemberActionCreate(
            action_type=MemberActionType.SEND_DM,
            payload={"message": message, "source": "platform_superadmin"},
        ),
    )
    return {"id": str(action.id), "status": action.status.value, "guild_id": str(guild.guild_id)}
