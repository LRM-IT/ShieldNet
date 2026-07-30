from __future__ import annotations

from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import SessionLocal
from .models import VerificationAudit, VerificationSettings, VerifiedMember
from .schemas import MemberUpdatePayload, SettingsPayload
from .service import get_or_create_settings, reset_member, save_settings

router = APIRouter(prefix="/plugins/verification-level1", tags=["Verification Level 1"])


async def db_session():
    async with SessionLocal() as session:
        yield session


def model_dict(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


@router.get("/{guild_id}/settings")
async def read_settings(guild_id: int, session: AsyncSession = Depends(db_session)):
    return model_dict(await get_or_create_settings(session, guild_id))


@router.put("/{guild_id}/settings")
async def update_settings(
    guild_id: int,
    payload: SettingsPayload,
    session: AsyncSession = Depends(db_session),
):
    return model_dict(await save_settings(session, guild_id, payload))


@router.get("/{guild_id}/members")
async def members(
    guild_id: int,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(db_session),
):
    stmt = select(VerifiedMember).where(VerifiedMember.guild_id == guild_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            VerifiedMember.nickname.ilike(pattern)
            | VerifiedMember.alliance.ilike(pattern)
            | VerifiedMember.discord_name.ilike(pattern)
        )
    stmt = stmt.order_by(desc(VerifiedMember.updated_at)).limit(min(limit, 500)).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return [model_dict(row) for row in rows]


@router.get("/{guild_id}/audit")
async def audit(
    guild_id: int,
    limit: int = 100,
    session: AsyncSession = Depends(db_session),
):
    stmt = (
        select(VerificationAudit)
        .where(VerificationAudit.guild_id == guild_id)
        .order_by(desc(VerificationAudit.created_at))
        .limit(min(limit, 500))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [model_dict(row) for row in rows]


@router.delete("/{guild_id}/members/{user_id}")
async def delete_member(
    guild_id: int,
    user_id: int,
    session: AsyncSession = Depends(db_session),
):
    return {"ok": await reset_member(session, guild_id, user_id)}
