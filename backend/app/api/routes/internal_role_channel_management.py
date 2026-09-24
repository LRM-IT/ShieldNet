import uuid
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.role_channel_management import DiscordStructureChange, DiscordBulkRoleOperation
from app.models.plugins import GuildPluginInstallation
from app.schemas.role_channel_management import StructureResultRequest, BulkRoleResultRequest
from app.api.routes.plugin_first_introduction import _groups

router = APIRouter(prefix="/internal/discord-management", tags=["Internal Discord Management"], dependencies=[Depends(verify_internal_service_token)])

@router.get("/pending")
async def pending(limit: int = Query(25, ge=1, le=100), session: AsyncSession = Depends(get_db_session)):
    changes = (await session.execute(select(DiscordStructureChange).where(DiscordStructureChange.status == "pending").order_by(DiscordStructureChange.created_at).limit(limit))).scalars().all()
    bulk = (await session.execute(select(DiscordBulkRoleOperation).where(DiscordBulkRoleOperation.status == "pending").order_by(DiscordBulkRoleOperation.created_at).limit(limit))).scalars().all()
    serialized=[]
    for x in changes:
        data=dict(x.payload or {})
        parent_change_id=data.pop("_parent_change_id",None)
        if parent_change_id:
            parent=await session.get(DiscordStructureChange,uuid.UUID(parent_change_id))
            parent_id=((parent.payload or {}).get("_result") or {}).get("channel_id") if parent else None
            if not parent_id:
                continue
            data["parent_id"]=parent_id
        serialized.append({"id":str(x.id),"guild_id":x.guild_id,"object_type":x.object_type,"operation":x.operation,"target_id":x.target_id,"payload":data})
    return {
        "changes": serialized,
        "bulk_roles": [{"id": str(x.id), "guild_id": x.guild_id, "discord_role_id": x.discord_role_id, "operation": x.operation, "member_ids": x.member_ids} for x in bulk],
    }

@router.post("/changes/{item_id}/result")
async def change_result(item_id: uuid.UUID, payload: StructureResultRequest, session: AsyncSession = Depends(get_db_session)):
    item = await session.get(DiscordStructureChange, item_id)
    if not item: raise HTTPException(404, "Change not found")
    item.status = payload.status; item.result_message = payload.message; item.payload = {**(item.payload or {}), "_result": payload.data}; item.completed_at = datetime.now(UTC)
    if (payload.status == "completed" and item.payload.get("_plugin") == "first_introduction"
            and item.payload.get("language_code") and payload.data.get("role_id")):
        installation = await session.scalar(select(GuildPluginInstallation).where(
            GuildPluginInstallation.guild_id == item.guild_id,
            GuildPluginInstallation.plugin_key == "first_introduction").with_for_update())
        if installation:
            config = dict(installation.configuration or {})
            groups = _groups(config)
            group = next((entry for entry in groups if entry["id"] == item.payload.get("_group_id", "r1")), None)
            roles = dict(group.get("language_roles") or {}) if group else {}
            code = item.payload["language_code"]
            if group and not roles.get(code):
                roles[code] = str(payload.data["role_id"])
                group["language_roles"] = roles
                config["groups"] = groups
                installation.configuration = config
    await session.commit(); return {"status": "ok"}

@router.post("/bulk-roles/{item_id}/result")
async def bulk_result(item_id: uuid.UUID, payload: BulkRoleResultRequest, session: AsyncSession = Depends(get_db_session)):
    item = await session.get(DiscordBulkRoleOperation, item_id)
    if not item: raise HTTPException(404, "Bulk role operation not found")
    item.status = payload.status; item.processed_count = payload.processed_count; item.failed_count = payload.failed_count; item.result = payload.result; item.completed_at = datetime.now(UTC)
    await session.commit(); return {"status": "ok"}
