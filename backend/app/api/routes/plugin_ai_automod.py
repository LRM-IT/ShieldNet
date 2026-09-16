from __future__ import annotations
import json,re
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.moderation import ModerationCase
from app.models.plugins import GuildPluginInstallation
from app.services.ai_runtime import AIRuntimeService

router=APIRouter(tags=["AI AutoMod plugin"])
internal_router=APIRouter(prefix="/internal/plugin-ai-automod",tags=["Internal AI AutoMod"],dependencies=[Depends(verify_internal_service_token)])
DEFAULT={"channel_mode":"all","channel_ids":[],"excluded_channel_ids":[],"ignored_role_ids":[],"categories":["harassment","hate","threats","sexual","self-harm","spam","scam"],"threshold":0.82,"delete_message":True,"warn_member":True,"timeout_minutes":0,"create_case":True,"log_channel_id":None,"warning_text":"Your message was removed by server moderation: {reason}"}

class SettingsInput(BaseModel):
    channel_mode:str="all";channel_ids:list[str]=Field(default_factory=list,max_length=100);excluded_channel_ids:list[str]=Field(default_factory=list,max_length=100);ignored_role_ids:list[str]=Field(default_factory=list,max_length=100);categories:list[str]=Field(min_length=1,max_length=20);threshold:float=Field(default=.82,ge=.5,le=1);delete_message:bool=True;warn_member:bool=True;timeout_minutes:int=Field(default=0,ge=0,le=40320);create_case:bool=True;log_channel_id:str|None=None;warning_text:str=Field(default=DEFAULT["warning_text"],max_length=1000)
    @field_validator("channel_mode")
    @classmethod
    def mode(cls,v):
        if v not in {"all","selected"}:raise ValueError("Unsupported channel mode")
        return v

class AnalyzeInput(BaseModel):
    guild_id:int;discord_user_id:int;channel_id:int;message_id:int;content:str=Field(max_length=8000);role_ids:list[int]=Field(default_factory=list,max_length=100);message_url:str|None=None

async def installation(session,guild_id):return await session.scalar(select(GuildPluginInstallation).where(GuildPluginInstallation.guild_id==guild_id,GuildPluginInstallation.plugin_key=="ai_automod"))
def config(item):return {**DEFAULT,**((item.configuration or {}) if item else {})}
async def response(session,guild_id):
    item=await installation(session,guild_id);return{"installed":item is not None,"enabled":bool(item and item.enabled),**config(item)}

@router.get("/discord/guilds/{guild_id}/plugins/ai-automod/settings")
async def get_settings(guild_id:int,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_module(session,user,guild_id,"plugins");return await response(session,guild_id)

@router.put("/discord/guilds/{guild_id}/plugins/ai-automod/settings")
async def save_settings(guild_id:int,payload:SettingsInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_module(session,user,guild_id,"plugins");item=await installation(session,guild_id)
    if not item:raise HTTPException(409,"Install AI AutoMod first")
    item.configuration=payload.model_dump();await session.commit();return await response(session,guild_id)

@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_configuration(guild_id:int,session:AsyncSession=Depends(get_db_session)):return await response(session,guild_id)

@internal_router.post("/analyze")
async def analyze(payload:AnalyzeInput,session:AsyncSession=Depends(get_db_session)):
    item=await installation(session,payload.guild_id);cfg=config(item)
    if not item or not item.enabled:return{"processed":False,"flagged":False}
    channel=str(payload.channel_id);roles={str(x) for x in payload.role_ids}
    if channel in cfg["excluded_channel_ids"] or roles.intersection(cfg["ignored_role_ids"]):return{"processed":False,"flagged":False}
    if cfg["channel_mode"]=="selected" and channel not in cfg["channel_ids"]:return{"processed":False,"flagged":False}
    prompt=("Moderate this Discord message for these categories: "+", ".join(cfg["categories"])+". "
      "Consider context, jokes and quoted text. Return strict JSON only: "
      '{"flagged":true,"confidence":0.95,"category":"harassment","reason":"short reason"}.\nMessage:\n'+payload.content)
    _,result=await AIRuntimeService(session).execute(guild_id=payload.guild_id,module_key="ai_automod",capability="moderation",input_text=prompt,max_output_tokens=300)
    try:data=json.loads(re.sub(r"^```(?:json)?|```$","",result.text.strip(),flags=re.I).strip())
    except Exception as exc:raise HTTPException(502,"AI moderation returned invalid JSON") from exc
    confidence=max(0,min(1,float(data.get("confidence") or 0)));flagged=bool(data.get("flagged")) and confidence>=cfg["threshold"]
    reason=str(data.get("reason") or "Policy violation")[:1000];category=str(data.get("category") or "other")[:64]
    case_id=None
    if flagged and cfg["create_case"]:
        case=ModerationCase(guild_id=payload.guild_id,reported_discord_user_id=payload.discord_user_id,title=f"AI AutoMod: {category}",description=f"{reason}\n\nMessage: {payload.content[:2000]}\n{payload.message_url or ''}",severity="high" if confidence>=.93 else "medium",priority="high" if confidence>=.93 else "normal",status="open")
        session.add(case);await session.commit();case_id=str(case.id)
    return{"processed":True,"flagged":flagged,"confidence":confidence,"category":category,"reason":reason,"case_id":case_id,"actions":{"delete_message":cfg["delete_message"],"warn_member":cfg["warn_member"],"timeout_minutes":cfg["timeout_minutes"],"log_channel_id":cfg["log_channel_id"],"warning_text":cfg["warning_text"]}}
