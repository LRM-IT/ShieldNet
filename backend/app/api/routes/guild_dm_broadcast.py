from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User

router = APIRouter(tags=["Guild DM Broadcast"])

class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=2000)
    role_ids: list[int] = Field(default_factory=list)
    exclude_bots: bool = True
    delay_ms: int = Field(default=1200, ge=750, le=10000)

class DeliveryResult(BaseModel):
    status: str
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    error: str | None = None
    details: list[dict[str, Any]] = Field(default_factory=list)

async def auth(guild_id:int,user:User,session:AsyncSession)->None:
    await require_guild_management(session,user,guild_id)

@router.get("/discord/guilds/{guild_id}/plugins/guild-dm-broadcast/dashboard")
async def dashboard(guild_id:int,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await auth(guild_id,current_user,session)
    row=(await session.execute(text("""
    SELECT count(*)::int total,
    count(*) FILTER(WHERE status='queued')::int queued,
    count(*) FILTER(WHERE status='running')::int running,
    count(*) FILTER(WHERE status='completed')::int completed,
    coalesce(sum(sent_count),0)::int sent,
    coalesce(sum(failed_count),0)::int failed
    FROM plugin_guild_dm_broadcast.campaigns WHERE guild_id=:g
    """),{"g":guild_id})).mappings().one()
    return dict(row)

@router.get("/discord/guilds/{guild_id}/plugins/guild-dm-broadcast/campaigns")
async def list_campaigns(guild_id:int,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await auth(guild_id,current_user,session)
    rows=(await session.execute(text("""
    SELECT id,guild_id,name,message,role_ids,exclude_bots,delay_ms,status,
    total_count,sent_count,failed_count,skipped_count,last_error,created_at,
    started_at,finished_at,cancelled_at
    FROM plugin_guild_dm_broadcast.campaigns WHERE guild_id=:g
    ORDER BY created_at DESC LIMIT 100
    """),{"g":guild_id})).mappings().all()
    return {"items":[dict(x) for x in rows]}

@router.post("/discord/guilds/{guild_id}/plugins/guild-dm-broadcast/campaigns",status_code=status.HTTP_201_CREATED)
async def create_campaign(guild_id:int,payload:CampaignCreate,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await auth(guild_id,current_user,session)
    enabled=(await session.execute(text("""
    SELECT enabled FROM plugins.guild_installations
    WHERE guild_id=:g AND plugin_key='guild-dm-broadcast'
    """),{"g":guild_id})).scalar_one_or_none()
    if enabled is not True:
        raise HTTPException(409,"Guild DM Broadcast plugin is not enabled")
    cid=uuid.uuid4(); now=datetime.now(timezone.utc)
    await session.execute(text("""
    INSERT INTO plugin_guild_dm_broadcast.campaigns
    (id,guild_id,name,message,role_ids,exclude_bots,delay_ms,status,
    created_by_user_id,created_at,updated_at)
    VALUES(:id,:g,:n,:m,CAST(:r AS jsonb),:b,:d,'queued',:u,:now,:now)
    """),{"id":cid,"g":guild_id,"n":payload.name.strip(),"m":payload.message,
    "r":json.dumps([str(x) for x in payload.role_ids]),"b":payload.exclude_bots,
    "d":payload.delay_ms,"u":current_user.id,"now":now})
    await session.commit()
    return {"id":str(cid),"status":"queued"}

@router.post("/discord/guilds/{guild_id}/plugins/guild-dm-broadcast/campaigns/{campaign_id}/cancel")
async def cancel(guild_id:int,campaign_id:uuid.UUID,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await auth(guild_id,current_user,session)
    result=await session.execute(text("""
    UPDATE plugin_guild_dm_broadcast.campaigns SET status='cancelled',
    cancelled_at=now(),updated_at=now()
    WHERE id=:id AND guild_id=:g AND status IN('queued','running')
    """),{"id":campaign_id,"g":guild_id})
    await session.commit()
    if not result.rowcount: raise HTTPException(409,"Campaign cannot be cancelled")
    return {"status":"cancelled"}

internal_router=APIRouter(prefix="/internal/plugin-guild-dm-broadcast",
tags=["Internal Guild DM Broadcast"],
dependencies=[Depends(verify_internal_service_token)])

@internal_router.get("/campaigns/pending")
async def pending(session:AsyncSession=Depends(get_db_session)):
    row=(await session.execute(text("""
    SELECT id,guild_id,name,message,role_ids,exclude_bots,delay_ms
    FROM plugin_guild_dm_broadcast.campaigns WHERE status='queued'
    ORDER BY created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1
    """))).mappings().first()
    if row is None:return {"item":None}
    await session.execute(text("""
    UPDATE plugin_guild_dm_broadcast.campaigns SET status='running',
    started_at=now(),updated_at=now() WHERE id=:id AND status='queued'
    """),{"id":row["id"]})
    await session.commit()
    return {"item":dict(row)}

@internal_router.get("/campaigns/{campaign_id}/state")
async def state(campaign_id:uuid.UUID,session:AsyncSession=Depends(get_db_session)):
    value=(await session.execute(text("""
    SELECT status FROM plugin_guild_dm_broadcast.campaigns WHERE id=:id
    """),{"id":campaign_id})).scalar_one_or_none()
    return {"status":value or "missing"}

@internal_router.post("/campaigns/{campaign_id}/result")
async def result(campaign_id:uuid.UUID,payload:DeliveryResult,session:AsyncSession=Depends(get_db_session)):
    if payload.status not in {"completed","failed","cancelled"}:
        raise HTTPException(422,"Invalid status")
    await session.execute(text("""
    UPDATE plugin_guild_dm_broadcast.campaigns SET status=:s,sent_count=:sent,
    failed_count=:failed,skipped_count=:skipped,total_count=:total,
    last_error=:error,finished_at=CASE WHEN :s IN('completed','failed')
    THEN now() ELSE finished_at END,updated_at=now() WHERE id=:id
    """),{"id":campaign_id,"s":payload.status,"sent":payload.sent,
    "failed":payload.failed,"skipped":payload.skipped,
    "total":payload.sent+payload.failed+payload.skipped,"error":payload.error})
    for item in payload.details[-5000:]:
        await session.execute(text("""
        INSERT INTO plugin_guild_dm_broadcast.delivery_log
        (campaign_id,discord_user_id,status,error,created_at)
        VALUES(:c,:u,:s,:e,now())
        """),{"c":campaign_id,"u":int(item.get("discord_user_id",0)),
        "s":str(item.get("status","unknown"))[:32],
        "e":str(item.get("error"))[:2000] if item.get("error") else None})
    await session.commit()
    return {"status":"saved"}
