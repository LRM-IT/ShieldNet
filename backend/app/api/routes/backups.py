from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.services.audit_service import AuditService
from app.services.backup_service import BackupService

router = APIRouter(tags=["Backup Center"])

class BackupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)

class BackupRestore(BaseModel):
    confirmation: str

def brief(x):
    return {"id": str(x.id), "guild_id": x.guild_id, "name": x.name, "description": x.description, "status": x.status, "format_version": x.format_version, "object_count": x.object_count, "size_bytes": x.size_bytes, "created_at": x.created_at}

@router.get("/discord/guilds/{guild_id}/backups")
async def list_backups(guild_id:int, current_user:User=Depends(get_current_user), session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,current_user,guild_id)
    return [brief(x) for x in await BackupService(session).list(guild_id)]

@router.post("/discord/guilds/{guild_id}/backups", status_code=201)
async def create_backup(guild_id:int, payload:BackupCreate, current_user:User=Depends(get_current_user), session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,current_user,guild_id)
    item=await BackupService(session).create(guild_id,payload.name,payload.description,current_user.id)
    await AuditService(session).record(event_type="backup.created",guild_id=guild_id,actor_user_id=current_user.id,target_type="guild_backup",target_id=str(item.id),payload={"name":item.name,"object_count":item.object_count})
    await session.commit()
    return brief(item)

@router.get("/discord/guilds/{guild_id}/backups/{backup_id}")
async def get_backup(guild_id:int,backup_id:UUID,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,current_user,guild_id)
    item=await BackupService(session).get(backup_id,guild_id)
    if not item: raise HTTPException(status_code=404,detail="Backup not found")
    return {**brief(item),"snapshot":item.snapshot}

@router.get("/discord/guilds/{guild_id}/backups/{backup_id}/download")
async def download_backup(guild_id:int,backup_id:UUID,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    import json
    await require_guild_management(session,current_user,guild_id)
    item=await BackupService(session).get(backup_id,guild_id)
    if not item: raise HTTPException(status_code=404,detail="Backup not found")
    body=json.dumps(item.snapshot,ensure_ascii=False,indent=2,default=str)
    return Response(body,media_type="application/json",headers={"Content-Disposition":f'attachment; filename="shieldnet-guild-{guild_id}-{backup_id}.json"'})

@router.post("/discord/guilds/{guild_id}/backups/{backup_id}/restore-plan")
async def restore_plan(guild_id:int,backup_id:UUID,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,current_user,guild_id)
    item=await BackupService(session).get(backup_id,guild_id)
    if not item: raise HTTPException(status_code=404,detail="Backup not found")
    return await BackupService(session).restore_plan(item)

@router.post("/discord/guilds/{guild_id}/backups/{backup_id}/restore")
async def restore_backup(guild_id:int,backup_id:UUID,payload:BackupRestore,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,current_user,guild_id)
    if payload.confirmation != "RESTORE": raise HTTPException(status_code=422,detail="Restore confirmation is invalid")
    item=await BackupService(session).get(backup_id,guild_id)
    if not item: raise HTTPException(status_code=404,detail="Backup not found")
    restored=await BackupService(session).restore_configuration(item)
    await AuditService(session).record(event_type="backup.restored",guild_id=guild_id,actor_user_id=current_user.id,target_type="guild_backup",target_id=str(item.id),payload=restored)
    await session.commit()
    return {"status":"restored","backup_id":str(item.id),"restored":restored,"discord_structure_changed":False}

@router.delete("/discord/guilds/{guild_id}/backups/{backup_id}", status_code=204)
async def delete_backup(guild_id:int,backup_id:UUID,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,current_user,guild_id)
    if not await BackupService(session).remove(backup_id,guild_id): raise HTTPException(status_code=404,detail="Backup not found")
    await AuditService(session).record(event_type="backup.deleted",guild_id=guild_id,actor_user_id=current_user.id,target_type="guild_backup",target_id=str(backup_id))
    await session.commit()
