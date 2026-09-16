from __future__ import annotations
from datetime import UTC,datetime,timedelta
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.plugins import GuildPluginInstallation
from app.models.role_channel_management import DiscordStructureChange
router=APIRouter(tags=["Event Manager plugin"]);internal_router=APIRouter(prefix="/internal/plugin-event-manager",tags=["Internal Event Manager"],dependencies=[Depends(verify_internal_service_token)])
class EventInput(BaseModel):
 id:str=Field(min_length=1,max_length=32);name:str=Field(min_length=1,max_length=80);title:str=Field(min_length=1,max_length=100);description:str=Field(default="",max_length=2000);channel_id:str;starts_at:datetime;max_participants:int=Field(default=0,ge=0,le=10000);reminder_minutes:int=Field(default=30,ge=0,le=10080);enabled:bool=True
 @field_validator("starts_at")
 @classmethod
 def aware(cls,v):return v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)
class SettingsInput(BaseModel):events:list[EventInput]=Field(default_factory=list,max_length=100)
class PublishInput(BaseModel):event_id:str
class PanelResult(BaseModel):guild_id:int;event_id:str;channel_id:str;message_id:str
class RSVPInput(BaseModel):guild_id:int;event_id:str;discord_user_id:int;status:str
def rows(item):return[dict(x) for x in((item.configuration or {}).get("events",[]) if item else [])]
async def installation(session,guild_id,lock=False):
 q=select(GuildPluginInstallation).where(GuildPluginInstallation.guild_id==guild_id,GuildPluginInstallation.plugin_key=="event_manager");q=q.with_for_update() if lock else q;return await session.scalar(q)
async def response(session,guild_id):
 item=await installation(session,guild_id);return{"installed":item is not None,"enabled":bool(item and item.enabled),"events":rows(item)}
@router.get("/discord/guilds/{guild_id}/plugins/event-manager/settings")
async def get_settings(guild_id:int,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");return await response(session,guild_id)
@router.put("/discord/guilds/{guild_id}/plugins/event-manager/settings")
async def save_settings(guild_id:int,payload:SettingsInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id,True)
 if not item:raise HTTPException(409,"Install Event Manager first")
 old={x["id"]:x for x in rows(item)};saved=[]
 for event in payload.events:
  data=event.model_dump(mode="json");previous=old.get(event.id)or{};data.update({"message_id":previous.get("message_id"),"participants":previous.get("participants",{}),"reminded_at":previous.get("reminded_at")});saved.append(data)
 item.configuration={**(item.configuration or{}),"events":saved};await session.commit();return await response(session,guild_id)
@router.post("/discord/guilds/{guild_id}/plugins/event-manager/publish")
async def publish(guild_id:int,payload:PublishInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id);event=next((x for x in rows(item)if x["id"]==payload.event_id and x.get("enabled")),None)
 if not item or not item.enabled:raise HTTPException(409,"Enable Event Manager first")
 if not event:raise HTTPException(404,"Event not found")
 job=DiscordStructureChange(guild_id=guild_id,object_type="event_panel",operation="publish",payload={"event_id":event["id"]},preview={"safe_to_apply":True},status="pending",requested_by=user.id);session.add(job);await session.commit();return{"job_id":str(job.id)}
@router.get("/discord/guilds/{guild_id}/plugins/event-manager/jobs/{job_id}")
async def job(guild_id:int,job_id:UUID,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await session.get(DiscordStructureChange,job_id)
 if not item or item.guild_id!=guild_id or item.object_type!="event_panel":raise HTTPException(404,"Job not found")
 return{"status":item.status,"error":item.result_message}
@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_config(guild_id:int,session:AsyncSession=Depends(get_db_session)):return await response(session,guild_id)
@internal_router.post("/panel")
async def panel(payload:PanelResult,session:AsyncSession=Depends(get_db_session)):
 item=await installation(session,payload.guild_id,True);events=rows(item);event=next((x for x in events if x["id"]==payload.event_id),None)
 if not event or event.get("channel_id")!=payload.channel_id:raise HTTPException(422,"Event channel mismatch")
 event["message_id"]=payload.message_id;item.configuration={**(item.configuration or{}),"events":events};await session.commit();return{"ok":True}
@internal_router.post("/rsvp")
async def rsvp(payload:RSVPInput,session:AsyncSession=Depends(get_db_session)):
 if payload.status not in{"going","maybe","declined"}:raise HTTPException(422,"Invalid RSVP")
 item=await installation(session,payload.guild_id,True);events=rows(item);event=next((x for x in events if x["id"]==payload.event_id and x.get("enabled")),None)
 if not item or not item.enabled or not event:raise HTTPException(404,"Event unavailable")
 participants=dict(event.get("participants")or{});current=participants.get(str(payload.discord_user_id))
 if current==payload.status:participants.pop(str(payload.discord_user_id),None)
 else:
  if payload.status=="going" and event.get("max_participants") and sum(v=="going" for v in participants.values())>=int(event["max_participants"]):raise HTTPException(409,"Event is full")
  participants[str(payload.discord_user_id)]=payload.status
 event["participants"]=participants;item.configuration={**(item.configuration or{}),"events":events};await session.commit();return{"participants":participants}
@internal_router.get("/reminders")
async def reminders(session:AsyncSession=Depends(get_db_session)):
 now=datetime.now(UTC);items=(await session.execute(select(GuildPluginInstallation).where(GuildPluginInstallation.plugin_key=="event_manager",GuildPluginInstallation.enabled.is_(True)).with_for_update())).scalars().all();due=[]
 for item in items:
  events=rows(item);changed=False
  for event in events:
   start=datetime.fromisoformat(str(event["starts_at"]).replace("Z","+00:00"));minutes=int(event.get("reminder_minutes")or 0)
   if event.get("enabled") and event.get("message_id") and not event.get("reminded_at") and now>=start-timedelta(minutes=minutes) and now<start:
    due.append({"guild_id":item.guild_id,**event});event["reminded_at"]=now.isoformat();changed=True
  if changed:item.configuration={**(item.configuration or{}),"events":events}
 await session.commit();return{"events":due}

