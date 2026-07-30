from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import VerificationAudit, VerificationSettings, VerifiedMember
from .schemas import SettingsPayload


async def get_or_create_settings(session: AsyncSession, guild_id: int) -> VerificationSettings:
    settings = await session.get(VerificationSettings, guild_id)
    if settings:
        return settings
    settings = VerificationSettings(guild_id=guild_id)
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings


async def save_settings(
    session: AsyncSession, guild_id: int, payload: SettingsPayload
) -> VerificationSettings:
    settings = await get_or_create_settings(session, guild_id)
    for key, value in payload.model_dump().items():
        setattr(settings, key, value)
    settings.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(settings)
    return settings


def render_nickname(settings: VerificationSettings, alliance: str, nickname: str) -> tuple[str, str, str]:
    if settings.trim_values:
        alliance = alliance.strip()
        nickname = nickname.strip()
    if settings.alliance_uppercase:
        alliance = alliance.upper()

    if not alliance:
        raise ValueError("Alliance is required")
    if not nickname:
        raise ValueError("Nickname is required")
    if len(alliance) > settings.max_alliance_length:
        raise ValueError(f"Alliance is longer than {settings.max_alliance_length} characters")
    if len(nickname) > settings.max_nickname_length:
        raise ValueError(f"Nickname is longer than {settings.max_nickname_length} characters")

    rendered = settings.nickname_mask.replace("{ALLIANCE}", alliance).replace("{NICKNAME}", nickname)
    rendered = " ".join(rendered.split())
    if len(rendered) > 32:
        raise ValueError("Resulting Discord nickname is longer than 32 characters")
    return alliance, nickname, rendered


async def upsert_member(
    session: AsyncSession,
    *,
    guild_id: int,
    user_id: int,
    discord_name: str,
    alliance: str,
    nickname: str,
    rendered_nickname: str,
    verified_by: str = "self",
) -> tuple[VerifiedMember, VerifiedMember | None]:
    old = await session.get(VerifiedMember, {"guild_id": guild_id, "user_id": user_id})
    old_snapshot = None
    if old:
        old_snapshot = VerifiedMember(
            guild_id=old.guild_id,
            user_id=old.user_id,
            discord_name=old.discord_name,
            alliance=old.alliance,
            nickname=old.nickname,
            rendered_nickname=old.rendered_nickname,
            verified_by=old.verified_by,
        )
        old.discord_name = discord_name
        old.alliance = alliance
        old.nickname = nickname
        old.rendered_nickname = rendered_nickname
        old.updated_at = datetime.now(timezone.utc)
        old.verified_by = verified_by
        member = old
    else:
        member = VerifiedMember(
            guild_id=guild_id,
            user_id=user_id,
            discord_name=discord_name,
            alliance=alliance,
            nickname=nickname,
            rendered_nickname=rendered_nickname,
            verified_by=verified_by,
        )
        session.add(member)

    await session.flush()
    return member, old_snapshot


async def add_audit(session: AsyncSession, **kwargs) -> VerificationAudit:
    row = VerificationAudit(**kwargs)
    session.add(row)
    await session.flush()
    return row


async def reset_member(session: AsyncSession, guild_id: int, user_id: int) -> bool:
    result = await session.execute(
        delete(VerifiedMember).where(
            VerifiedMember.guild_id == guild_id,
            VerifiedMember.user_id == user_id,
        )
    )
    await session.commit()
    return bool(result.rowcount)
