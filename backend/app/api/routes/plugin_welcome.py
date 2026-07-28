from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User

router = APIRouter(tags=["Welcome plugin"])
internal_router = APIRouter(
    prefix="/internal/plugin-welcome",
    tags=["Internal Welcome plugin"],
    dependencies=[Depends(verify_internal_service_token)],
)

DEFAULT_MESSAGE = (
    "👋 Welcome, {mention}!\n\n"
    "Welcome to **{guild}**.\n\n"
    "Please continue to {verification_channel} and complete verification."
)

class WelcomeSettings(BaseModel):
    enabled: bool = True
    welcome_channel_id: int | None = None
    verification_channel_id: int | None = None
    required_role_id: int | None = None
    message_template: str = Field(default=DEFAULT_MESSAGE, min_length=1, max_length=2000)
    repeat_enabled: bool = True
    repeat_minutes: int = Field(default=5, ge=1, le=1440)
    max_reminders: int = Field(default=12, ge=0, le=1000)
    delete_after_verified: bool = True
    ignore_bots: bool = True

class InternalJoin(BaseModel):
    guild_id: int
    user_id: int
    username: str
    display_name: str
    guild_name: str
    bot: bool = False

class InternalRoleUpdate(BaseModel):
    guild_id: int
    user_id: int
    role_ids: list[int] = Field(default_factory=list)

class InternalLeave(BaseModel):
    guild_id: int
    user_id: int

class InternalMessageResult(BaseModel):
    task_id: str
    message_id: int | None = None
    error: str | None = None

async def _auth(guild_id: int, user: User, session: AsyncSession) -> None:
    await require_guild_management(session, user, guild_id)

def _settings(row: Any | None) -> dict[str, Any]:
    if row is None:
        return WelcomeSettings().model_dump()
    return dict(row)

@router.get("/discord/guilds/{guild_id}/plugins/welcome/settings")
async def get_settings(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _auth(guild_id, current_user, session)
    row = (
        await session.execute(
            text("""
                SELECT enabled,welcome_channel_id,verification_channel_id,
                       required_role_id,message_template,repeat_enabled,
                       repeat_minutes,max_reminders,delete_after_verified,
                       ignore_bots
                FROM plugin_welcome.settings
                WHERE guild_id=:guild_id
            """),
            {"guild_id": guild_id},
        )
    ).mappings().first()
    return _settings(row)

@router.put("/discord/guilds/{guild_id}/plugins/welcome/settings")
async def save_settings(
    guild_id: int,
    payload: WelcomeSettings,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _auth(guild_id, current_user, session)
    if payload.enabled and (
        payload.welcome_channel_id is None
        or payload.verification_channel_id is None
        or payload.required_role_id is None
    ):
        raise HTTPException(
            422,
            "Welcome channel, verification channel and required role are required",
        )
    values = payload.model_dump()
    values["guild_id"] = guild_id
    await session.execute(
        text("""
            INSERT INTO plugin_welcome.settings(
                guild_id,enabled,welcome_channel_id,verification_channel_id,
                required_role_id,message_template,repeat_enabled,repeat_minutes,
                max_reminders,delete_after_verified,ignore_bots,updated_at
            ) VALUES(
                :guild_id,:enabled,:welcome_channel_id,:verification_channel_id,
                :required_role_id,:message_template,:repeat_enabled,:repeat_minutes,
                :max_reminders,:delete_after_verified,:ignore_bots,now()
            )
            ON CONFLICT(guild_id) DO UPDATE SET
                enabled=excluded.enabled,
                welcome_channel_id=excluded.welcome_channel_id,
                verification_channel_id=excluded.verification_channel_id,
                required_role_id=excluded.required_role_id,
                message_template=excluded.message_template,
                repeat_enabled=excluded.repeat_enabled,
                repeat_minutes=excluded.repeat_minutes,
                max_reminders=excluded.max_reminders,
                delete_after_verified=excluded.delete_after_verified,
                ignore_bots=excluded.ignore_bots,
                updated_at=now()
        """),
        values,
    )
    await session.commit()
    return payload.model_dump()

@router.get("/discord/guilds/{guild_id}/plugins/welcome/tasks")
async def list_tasks(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await _auth(guild_id, current_user, session)
    rows = (
        await session.execute(
            text("""
                SELECT id,user_id,username,status,sent_count,next_send_at,
                       created_at,completed_at,last_error
                FROM plugin_welcome.tasks
                WHERE guild_id=:guild_id
                ORDER BY created_at DESC
                LIMIT 100
            """),
            {"guild_id": guild_id},
        )
    ).mappings().all()
    return {"items": [dict(row) for row in rows]}

@internal_router.get("/guilds/{guild_id}/settings")
async def internal_settings(
    guild_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    row = (
        await session.execute(
            text("""
                SELECT enabled,welcome_channel_id,verification_channel_id,
                       required_role_id,message_template,repeat_enabled,
                       repeat_minutes,max_reminders,delete_after_verified,
                       ignore_bots
                FROM plugin_welcome.settings
                WHERE guild_id=:guild_id
            """),
            {"guild_id": guild_id},
        )
    ).mappings().first()
    return {"settings": dict(row) if row else None}

@internal_router.post("/member-join")
async def member_join(
    payload: InternalJoin,
    session: AsyncSession = Depends(get_db_session),
):
    settings = (
        await session.execute(
            text("""
                SELECT * FROM plugin_welcome.settings
                WHERE guild_id=:guild_id AND enabled=true
            """),
            {"guild_id": payload.guild_id},
        )
    ).mappings().first()
    if settings is None:
        return {"status": "disabled"}
    if payload.bot and settings["ignore_bots"]:
        return {"status": "ignored"}

    row = (
        await session.execute(
            text("""
                INSERT INTO plugin_welcome.tasks(
                    guild_id,user_id,username,display_name,guild_name,status,
                    sent_count,next_send_at,created_at,updated_at
                ) VALUES(
                    :guild_id,:user_id,:username,:display_name,:guild_name,
                    'waiting',0,now(),now(),now()
                )
                ON CONFLICT(guild_id,user_id) DO UPDATE SET
                    username=excluded.username,
                    display_name=excluded.display_name,
                    guild_name=excluded.guild_name,
                    status='waiting',
                    sent_count=0,
                    next_send_at=now(),
                    completed_at=NULL,
                    last_error=NULL,
                    updated_at=now()
                RETURNING id
            """),
            payload.model_dump(),
        )
    ).scalar_one()
    await session.commit()
    return {"status": "queued", "task_id": str(row)}

@internal_router.post("/member-roles")
async def member_roles(
    payload: InternalRoleUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    settings = (
        await session.execute(
            text("""
                SELECT required_role_id,delete_after_verified
                FROM plugin_welcome.settings
                WHERE guild_id=:guild_id
            """),
            {"guild_id": payload.guild_id},
        )
    ).mappings().first()
    if settings is None or settings["required_role_id"] not in payload.role_ids:
        return {"status": "waiting"}

    rows = (
        await session.execute(
            text("""
                UPDATE plugin_welcome.tasks
                SET status='completed',completed_at=now(),updated_at=now()
                WHERE guild_id=:guild_id AND user_id=:user_id
                  AND status='waiting'
                RETURNING id
            """),
            payload.model_dump(),
        )
    ).scalars().all()
    await session.commit()
    return {
        "status": "completed",
        "task_ids": [str(item) for item in rows],
        "delete_messages": bool(settings["delete_after_verified"]),
    }

@internal_router.post("/member-left")
async def member_left(
    payload: InternalLeave,
    session: AsyncSession = Depends(get_db_session),
):
    rows = (
        await session.execute(
            text("""
                UPDATE plugin_welcome.tasks
                SET status='member_left',completed_at=now(),updated_at=now()
                WHERE guild_id=:guild_id AND user_id=:user_id
                  AND status='waiting'
                RETURNING id
            """),
            payload.model_dump(),
        )
    ).scalars().all()
    await session.commit()
    return {"task_ids": [str(item) for item in rows]}

@internal_router.get("/due")
async def due(session: AsyncSession = Depends(get_db_session)):
    row = (
        await session.execute(
            text("""
                SELECT t.id,t.guild_id,t.user_id,t.username,t.display_name,
                       t.guild_name,t.sent_count,
                       s.welcome_channel_id,s.verification_channel_id,
                       s.required_role_id,s.message_template,
                       s.repeat_enabled,s.repeat_minutes,s.max_reminders
                FROM plugin_welcome.tasks t
                JOIN plugin_welcome.settings s ON s.guild_id=t.guild_id
                WHERE t.status='waiting'
                  AND s.enabled=true
                  AND t.next_send_at<=now()
                  AND (
                    t.sent_count=0 OR
                    (s.repeat_enabled=true AND
                     (s.max_reminders=0 OR t.sent_count<s.max_reminders))
                  )
                ORDER BY t.next_send_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            """)
        )
    ).mappings().first()
    if row is None:
        return {"item": None}
    await session.execute(
        text("""
            UPDATE plugin_welcome.tasks
            SET next_send_at=now()+make_interval(mins=>:minutes),
                updated_at=now()
            WHERE id=:id
        """),
        {"id": row["id"], "minutes": int(row["repeat_minutes"])},
    )
    await session.commit()
    return {"item": dict(row)}

@internal_router.post("/message-result")
async def message_result(
    payload: InternalMessageResult,
    session: AsyncSession = Depends(get_db_session),
):
    if payload.message_id:
        await session.execute(
            text("""
                INSERT INTO plugin_welcome.messages(task_id,message_id,created_at)
                VALUES(CAST(:task_id AS uuid),:message_id,now())
                ON CONFLICT(task_id,message_id) DO NOTHING
            """),
            payload.model_dump(),
        )
        await session.execute(
            text("""
                UPDATE plugin_welcome.tasks
                SET sent_count=sent_count+1,last_error=NULL,updated_at=now()
                WHERE id=CAST(:task_id AS uuid)
            """),
            payload.model_dump(),
        )
    elif payload.error:
        await session.execute(
            text("""
                UPDATE plugin_welcome.tasks
                SET last_error=:error,updated_at=now()
                WHERE id=CAST(:task_id AS uuid)
            """),
            payload.model_dump(),
        )
    await session.commit()
    return {"status": "saved"}

@internal_router.get("/tasks/{task_id}/messages")
async def task_messages(
    task_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    rows = (
        await session.execute(
            text("""
                SELECT message_id FROM plugin_welcome.messages
                WHERE task_id=CAST(:task_id AS uuid)
                ORDER BY created_at
            """),
            {"task_id": task_id},
        )
    ).scalars().all()
    task = (
        await session.execute(
            text("""
                SELECT guild_id FROM plugin_welcome.tasks
                WHERE id=CAST(:task_id AS uuid)
            """),
            {"task_id": task_id},
        )
    ).scalar_one_or_none()
    return {"guild_id": task, "message_ids": list(rows)}

@internal_router.delete("/tasks/{task_id}/messages")
async def clear_messages(
    task_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    await session.execute(
        text("DELETE FROM plugin_welcome.messages WHERE task_id=CAST(:task_id AS uuid)"),
        {"task_id": task_id},
    )
    await session.commit()
    return {"status": "cleared"}
