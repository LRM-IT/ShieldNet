from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
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
    template_key: Literal["minimal", "community", "gaming", "clan", "support"] = "community"

STRUCTURES = {
    "minimal": [("START", [("text","welcome",True),("text","rules",False),("text","general",False)])],
    "community": [("INFORMATION", [("text","welcome",True),("text","rules",False),("text","announcements",False)]),("COMMUNITY",[("text","general",False),("text","introductions",False),("text","media",False)]),("VOICE",[("voice","Lobby",False),("voice","General",False)])],
    "gaming": [("START HERE", [("text","welcome",True),("text","rules",False),("text","choose-roles",False)]),("GAME",[("text","general",False),("text","looking-for-group",False),("text","clips-and-media",False)]),("VOICE",[("voice","Lobby",False),("voice","Squad 1",False),("voice","Squad 2",False)])],
    "clan": [("HEADQUARTERS", [("text","welcome",True),("text","announcements",False),("text","rules",False)]),("OPERATIONS",[("text","strategy",False),("text","events",False),("text","recruitment",False)]),("VOICE",[("voice","Command",False),("voice","Squad",False)])],
    "support": [("INFORMATION", [("text","welcome",True),("text","announcements",False),("text","faq",False)]),("SUPPORT",[("text","help-desk",False),("text","resolved-cases",False)]),("COMMUNITY",[("text","general",False)]),("VOICE",[("voice","Support room",False)])],
}

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
    ).order_by(DiscordStructureChange.created_at.desc()).limit(50))).scalars().all()
    by_kind={}
    for job in jobs: by_kind.setdefault(job.object_type,job)
    profile=by_kind.get("guild_profile"); channel=by_kind.get("wizard_system_channel"); check=by_kind.get("permission_check")
    batch=[job for job in jobs if profile and job.created_at>=profile.created_at]
    completed=bool(profile and channel and batch and all(job.status=="completed" for job in batch))
    result=(channel.payload or {}).get("_result",{}) if channel else {}
    configuration={"game":(profile.payload or {}).get("game","") if profile else "","description":(profile.payload or {}).get("description","") if profile else "","system_channel_id":result.get("channel_id"),"system_channel_name":(channel.payload or {}).get("name") if channel else None}
    return {"completed":completed,"running":any(job.status in {"pending","processing"} for job in batch),"failed_jobs":[change_payload(job) for job in batch if job.status=="failed"],"guild":{"name":guild.name,"icon_url":guild.icon_url},"permission_check":change_payload(check),"profile_job":change_payload(profile),"channel_job":change_payload(channel),"configuration":configuration}

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
    db.add(profile);await db.flush();queued=[profile];system_job=None
    for category_name, channels in STRUCTURES[payload.template_key]:
        category=DiscordStructureChange(guild_id=guild_id,object_type="category",operation="create",payload={"name":category_name},preview={"safe_to_apply":True,"wizard_plugin":True,"template":payload.template_key},status="pending",requested_by=user.id)
        db.add(category);await db.flush();queued.append(category)
        for channel_type,name,is_system in channels:
            actual_name=payload.system_channel_name.strip() if is_system else name
            item=DiscordStructureChange(guild_id=guild_id,object_type="wizard_system_channel" if is_system else "channel",operation="create",payload={"name":actual_name,"channel_type":channel_type,"topic":payload.description.strip() if is_system else None,"position":0 if is_system else None,"set_system_channel":is_system,"_parent_change_id":str(category.id)},preview={"safe_to_apply":True,"wizard_plugin":True,"template":payload.template_key},status="pending",requested_by=user.id)
            db.add(item);queued.append(item)
            if is_system: system_job=item
    await db.commit()
    return {"status":"queued","queued":len(queued),"profile_job_id":str(profile.id),"channel_job_id":str(system_job.id) if system_job else None}
