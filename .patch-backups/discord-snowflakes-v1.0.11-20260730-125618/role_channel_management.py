import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.models.guild_roles import DiscordGuildRole
from app.models.explorer import GuildChannel
from app.models.role_channel_management import DiscordStructureChange, DiscordBulkRoleOperation
from app.schemas.role_channel_management import StructureChangeRequest, StructureChangeApplyRequest, BulkRoleRequest

router = APIRouter(tags=["Role & Channel Management"])

def _serialize_change(item):
    return {
        "id": str(item.id), "guild_id": item.guild_id, "object_type": item.object_type,
        "operation": item.operation, "target_id": item.target_id, "payload": item.payload,
        "preview": item.preview, "status": item.status, "result_message": item.result_message,
        "created_at": item.created_at, "started_at": item.started_at, "completed_at": item.completed_at,
    }

async def _build_preview(session: AsyncSession, guild_id: int, payload: StructureChangeRequest):
    current = None
    warnings = []
    if payload.object_type == "role" and payload.target_id:
        role = (await session.execute(select(DiscordGuildRole).where(
            DiscordGuildRole.guild_id == guild_id,
            DiscordGuildRole.discord_role_id == payload.target_id,
        ))).scalar_one_or_none()
        if role:
            current = {"id": role.discord_role_id, "name": role.name, "position": role.position,
                       "color": role.color, "permissions": role.permissions,
                       "managed": role.managed, "assignable": role.assignable}
            if role.managed:
                warnings.append("Managed roles cannot be modified or deleted")
            if not role.assignable:
                warnings.append("Role is not below the bot's highest role")
    elif payload.object_type in {"channel", "category"} and payload.target_id:
        channel = (await session.execute(select(GuildChannel).where(
            GuildChannel.guild_id == guild_id,
            GuildChannel.discord_channel_id == payload.target_id,
        ))).scalar_one_or_none()
        if channel:
            current = {"id": channel.discord_channel_id, "name": channel.name,
                       "type": channel.channel_type, "parent_id": channel.parent_id,
                       "position": channel.position, "nsfw": channel.nsfw, "topic": channel.topic}
    return {
        "current": current,
        "requested": payload.payload,
        "operation": payload.operation,
        "object_type": payload.object_type,
        "target_id": payload.target_id,
        "warnings": warnings,
        "safe_to_apply": not warnings,
    }

@router.get("/discord/guilds/{guild_id}/structure")
async def get_structure(guild_id: int, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    roles = (await session.execute(select(DiscordGuildRole).where(DiscordGuildRole.guild_id == guild_id).order_by(DiscordGuildRole.position.desc()))).scalars().all()
    channels = (await session.execute(select(GuildChannel).where(GuildChannel.guild_id == guild_id).order_by(GuildChannel.position.asc()))).scalars().all()
    return {
        "roles": [{"id": x.discord_role_id, "name": x.name, "position": x.position, "color": x.color, "permissions": x.permissions, "managed": x.managed, "assignable": x.assignable} for x in roles],
        "channels": [{"id": x.discord_channel_id, "parent_id": x.parent_id, "name": x.name, "type": x.channel_type, "position": x.position, "nsfw": x.nsfw, "topic": x.topic} for x in channels],
    }

@router.post("/discord/guilds/{guild_id}/structure/preview")
async def preview_change(guild_id: int, payload: StructureChangeRequest, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    return await _build_preview(session, guild_id, payload)

@router.post("/discord/guilds/{guild_id}/structure/changes")
async def create_change(guild_id: int, payload: StructureChangeRequest, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    preview = await _build_preview(session, guild_id, payload)
    item = DiscordStructureChange(
        guild_id=guild_id, object_type=payload.object_type, operation=payload.operation,
        target_id=payload.target_id, payload=payload.payload, preview=preview,
        status="preview" if payload.preview_only else "pending", requested_by=current_user.id,
    )
    session.add(item); await session.commit(); await session.refresh(item)
    return _serialize_change(item)

@router.post("/discord/guilds/{guild_id}/structure/changes/{change_id}/apply")
async def apply_change(guild_id: int, change_id: uuid.UUID, payload: StructureChangeApplyRequest, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    item = (await session.execute(select(DiscordStructureChange).where(
        DiscordStructureChange.id == change_id, DiscordStructureChange.guild_id == guild_id
    ))).scalar_one_or_none()
    if not item: raise HTTPException(404, "Change not found")
    if not item.preview.get("safe_to_apply", True): raise HTTPException(409, "Change has blocking warnings")
    if item.status not in {"preview", "failed"}: raise HTTPException(409, "Change cannot be queued")
    item.status = "pending"; item.result_message = None
    await session.commit(); return _serialize_change(item)

@router.get("/discord/guilds/{guild_id}/structure/changes")
async def list_changes(guild_id: int, status: str | None = None, limit: int = Query(100, ge=1, le=500), current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    stmt = select(DiscordStructureChange).where(DiscordStructureChange.guild_id == guild_id)
    if status: stmt = stmt.where(DiscordStructureChange.status == status)
    rows = (await session.execute(stmt.order_by(DiscordStructureChange.created_at.desc()).limit(limit))).scalars().all()
    return [_serialize_change(x) for x in rows]

@router.post("/discord/guilds/{guild_id}/roles/bulk")
async def bulk_roles(guild_id: int, payload: BulkRoleRequest, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    role = (await session.execute(select(DiscordGuildRole).where(
        DiscordGuildRole.guild_id == guild_id, DiscordGuildRole.discord_role_id == payload.discord_role_id
    ))).scalar_one_or_none()
    if not role: raise HTTPException(404, "Role not found")
    if role.managed or not role.assignable: raise HTTPException(409, "Role cannot be assigned by the bot")
    item = DiscordBulkRoleOperation(guild_id=guild_id, discord_role_id=payload.discord_role_id, operation=payload.operation, member_ids=list(dict.fromkeys(payload.member_ids)), requested_by=current_user.id)
    session.add(item); await session.commit(); await session.refresh(item)
    return {"id": str(item.id), "status": item.status, "member_count": len(item.member_ids)}
