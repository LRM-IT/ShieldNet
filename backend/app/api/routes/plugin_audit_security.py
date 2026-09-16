from __future__ import annotations
from datetime import UTC,datetime
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.plugins import GuildPluginInstallation
router=APIRouter(tags=["Audit & Security plugin"]);internal_router=APIRouter(prefix="/internal/plugin-audit-security",tags=["Internal Audit & Security"],dependencies=[Depends(verify_internal_service_token)])
EVENTS={"message_delete","message_edit","member_join","member_leave","member_roles","role_change","channel_change"}
class SettingsInput(BaseModel):
 log_channel_id:str|None=None;events:list[str]=Field(default_factory=lambda:sorted(EVENTS),max_length=20);retention:int=Field(default=200,ge=25,le=1000);mention_role_id:str|None=None
class EventInput(BaseModel):
 guild_id:int;event_type:str;actor_id:str|None=None;target_id:str|None=None;title:str=Field(max_length=200);description:str=Field(default="",max_length=2000);severity:str="info";metadata:dict=Field(default_factory=dict)
async def installation(session,guild_id,lock=False):
 q=select(GuildPluginInstallation).where(GuildPluginInstallation.guild_id==guild_id,GuildPluginInstallation.plugin_key=="audit_security");return await session.scalar(q.with_for_update()if lock else q)
def cfg(item):
 raw=item.configuration or{}if item else{};return{"log_channel_id":raw.get("log_channel_id"),"events":raw.get("events",sorted(EVENTS)),"retention":int(raw.get("retention",200)),"mention_role_id":raw.get("mention_role_id")}
def response(item):return{"installed":item is not None,"enabled":bool(item and item.enabled),**cfg(item),"audit_events":(item.configuration or{}).get("audit_events",[])if item else[]}
@router.get("/discord/guilds/{guild_id}/plugins/audit-security/settings")
async def get_settings(guild_id:int,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");return response(await installation(session,guild_id))
@router.put("/discord/guilds/{guild_id}/plugins/audit-security/settings")
async def save_settings(guild_id:int,payload:SettingsInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
 await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id,True)
 if not item:raise HTTPException(409,"Install Audit & Security first")
 unknown=set(payload.events)-EVENTS
 if unknown:raise HTTPException(422,f"Unknown events: {', '.join(sorted(unknown))}")
 item.configuration={**(item.configuration or{}),**payload.model_dump()};await session.commit();return response(item)
@internal_router.post("/event")
async def record(payload:EventInput,session:AsyncSession=Depends(get_db_session)):
 if payload.event_type not in EVENTS:raise HTTPException(422,"Unsupported event type")
 if payload.severity not in{"info","low","medium","high","critical"}:raise HTTPException(422,"Invalid severity")
 item=await installation(session,payload.guild_id,True)
 if not item or not item.enabled:return{"recorded":False}
 settings=cfg(item)
 if payload.event_type not in settings["events"]:return{"recorded":False}
 data=dict(item.configuration or{});events=list(data.get("audit_events")or[]);event={**payload.model_dump(),"created_at":datetime.now(UTC).isoformat()};events.insert(0,event);data["audit_events"]=events[:settings["retention"]];item.configuration=data;await session.commit()
 return{"recorded":True,"log_channel_id":settings["log_channel_id"],"mention_role_id":settings["mention_role_id"],"event":event}
