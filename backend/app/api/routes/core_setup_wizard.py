from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.models.discord import Guild
from app.models.role_channel_management import DiscordStructureChange

router = APIRouter(tags=["Core server setup wizard"])

class WizardApply(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    icon_data: str | None = Field(default=None, max_length=1_500_000)
    description: str = Field(default="", max_length=300)
    game: str = Field(default="", max_length=100)
    system_channel_name: str = Field(min_length=1, max_length=100)

def change_payload(item: DiscordStructureChange | None):
    if not item: return None
    return {"id":str(item.id),"status":item.status,"message":item.result_message,"result":(item.payload or {}).get("_result",{})}

@router.get("/discord/guilds/{guild_id}/setup-wizard")
async def state(guild_id:int,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db_session)):
    await require_guild_management(db,user,guild_id)
    guild=await db.get(Guild,guild_id)
    jobs=(await db.execute(select(DiscordStructureChange).where(
        DiscordStructureChange.guild_id==guild_id,
        DiscordStructureChange.preview["wizard_plugin"].as_boolean().is_(True),
    ).order_by(DiscordStructureChange.created_at.desc()).limit(10))).scalars().all()
    by_kind={}
    for job in jobs: by_kind.setdefault(job.object_type,job)
    profile=by_kind.get("guild_profile"); channel=by_kind.get("wizard_system_channel"); check=by_kind.get("permission_check")
    completed=bool(profile and channel and profile.status=="completed" and channel.status=="completed")
    result=(channel.payload or {}).get("_result",{}) if channel else {}
    configuration={"game":(profile.payload or {}).get("game","") if profile else "","description":(profile.payload or {}).get("description","") if profile else "","system_channel_id":result.get("channel_id"),"system_channel_name":(channel.payload or {}).get("name") if channel else None}
    return {"completed":completed,"guild":{"name":guild.name,"icon_url":guild.icon_url},"permission_check":change_payload(check),"profile_job":change_payload(profile),"channel_job":change_payload(channel),"configuration":configuration}

@router.post("/discord/guilds/{guild_id}/setup-wizard/check")
async def check(guild_id:int,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db_session)):
    await require_guild_management(db,user,guild_id)
    job=DiscordStructureChange(guild_id=guild_id,object_type="permission_check",operation="check",payload={},preview={"safe_to_apply":True,"wizard_plugin":True},status="pending",requested_by=user.id)
    db.add(job);await db.commit();return {"job_id":str(job.id)}

@router.post("/discord/guilds/{guild_id}/setup-wizard/apply")
async def apply(guild_id:int,payload:WizardApply,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db_session)):
    await require_guild_management(db,user,guild_id)
    pending=await db.scalar(select(DiscordStructureChange).where(DiscordStructureChange.guild_id==guild_id,DiscordStructureChange.preview["wizard_plugin"].as_boolean().is_(True),DiscordStructureChange.status.in_(["pending","processing"])))
    if pending: raise HTTPException(409,"Wizard setup is already running")
    profile=DiscordStructureChange(guild_id=guild_id,object_type="guild_profile",operation="update",payload={"name":payload.name.strip(),"icon_data":payload.icon_data,"description":payload.description.strip(),"game":payload.game.strip()},preview={"safe_to_apply":True,"wizard_plugin":True},status="pending",requested_by=user.id)
    channel=DiscordStructureChange(guild_id=guild_id,object_type="wizard_system_channel",operation="create",payload={"name":payload.system_channel_name.strip(),"topic":payload.description.strip() or None,"position":0,"set_system_channel":True},preview={"safe_to_apply":True,"wizard_plugin":True},status="pending",requested_by=user.id)
    db.add_all([profile,channel]);await db.commit()
    return {"status":"queued","profile_job_id":str(profile.id),"channel_job_id":str(channel.id)}
