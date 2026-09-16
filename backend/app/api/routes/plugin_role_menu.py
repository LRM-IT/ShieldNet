from __future__ import annotations

import re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.plugins import GuildPluginInstallation
from app.models.role_channel_management import DiscordStructureChange

router = APIRouter(tags=["Role Menu plugin"])
internal_router = APIRouter(prefix="/internal/plugin-role-menu", tags=["Internal Role Menu plugin"], dependencies=[Depends(verify_internal_service_token)])
DISCORD_ID = re.compile(r"^[0-9]{15,22}$")
PANEL_ID = re.compile(r"^[a-z0-9_-]{1,32}$")

class OptionInput(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    role_id: str
    emoji: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=100)
    @field_validator("role_id")
    @classmethod
    def valid_role(cls, value):
        if not DISCORD_ID.fullmatch(value): raise ValueError("Select a Discord role")
        return value

class PanelInput(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    enabled: bool = True
    channel_id: str | None = None
    required_role_id: str | None = None
    mode: str = "buttons"
    max_roles: int = Field(default=0, ge=0, le=25)
    options: list[OptionInput] = Field(default_factory=list, max_length=25)
    @field_validator("id")
    @classmethod
    def valid_id(cls, value):
        value=value.strip().lower()
        if not PANEL_ID.fullmatch(value): raise ValueError("Invalid panel ID")
        return value
    @field_validator("channel_id", "required_role_id")
    @classmethod
    def valid_discord_id(cls, value):
        if value is not None and not DISCORD_ID.fullmatch(value): raise ValueError("Select a Discord object")
        return value
    @field_validator("mode")
    @classmethod
    def valid_mode(cls, value):
        if value not in {"buttons", "select"}: raise ValueError("Unsupported menu mode")
        return value
    @model_validator(mode="after")
    def valid_options(self):
        ids=[item.role_id for item in self.options]
        if len(ids)!=len(set(ids)): raise ValueError("Roles in one panel must be unique")
        return self

class SettingsInput(BaseModel):
    panels: list[PanelInput] = Field(default_factory=list, max_length=20)
    @model_validator(mode="after")
    def unique_panels(self):
        if len({x.id for x in self.panels}) != len(self.panels): raise ValueError("Panel IDs must be unique")
        return self

class PublishInput(BaseModel): panel_id: str
class PanelResult(BaseModel): guild_id: int; panel_id: str; channel_id: str; message_id: str

async def installation(session, guild_id):
    return await session.scalar(select(GuildPluginInstallation).where(GuildPluginInstallation.guild_id==guild_id, GuildPluginInstallation.plugin_key=="role_menu"))

def panels(config): return [dict(item) for item in (config or {}).get("panels", [])]
async def settings(session, guild_id):
    item=await installation(session,guild_id)
    return {"installed":item is not None,"enabled":bool(item and item.enabled),"panels":panels(item.configuration if item else {})}

@router.get("/discord/guilds/{guild_id}/plugins/role-menu/settings")
async def get_settings(guild_id:int,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_module(session,user,guild_id,"plugins"); return await settings(session,guild_id)

@router.put("/discord/guilds/{guild_id}/plugins/role-menu/settings")
async def save_settings(guild_id:int,payload:SettingsInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_module(session,user,guild_id,"plugins"); item=await installation(session,guild_id)
    if not item: raise HTTPException(409,"Install Role Menu first")
    previous={x["id"]:x for x in panels(item.configuration)}; saved=[]
    for panel in payload.panels:
        if item.enabled and panel.enabled and (not panel.channel_id or not panel.options): raise HTTPException(422,f"{panel.name}: select a channel and at least one role")
        data=panel.model_dump(); old=previous.get(panel.id) or {}
        data["message_id"]=old.get("message_id") if old.get("channel_id")==panel.channel_id and old.get("options")==data["options"] else None
        saved.append(data)
    item.configuration={**(item.configuration or {}),"panels":saved}; await session.commit(); return await settings(session,guild_id)

@router.post("/discord/guilds/{guild_id}/plugins/role-menu/publish")
async def publish(guild_id:int,payload:PublishInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_module(session,user,guild_id,"plugins"); item=await installation(session,guild_id)
    panel=next((x for x in panels(item.configuration if item else {}) if x["id"]==payload.panel_id and x.get("enabled")),None)
    if not item or not item.enabled: raise HTTPException(409,"Enable Role Menu first")
    if not panel or not panel.get("channel_id") or not panel.get("options"): raise HTTPException(422,"Configure and enable this panel first")
    job=DiscordStructureChange(guild_id=guild_id,object_type="role_menu_panel",operation="publish",payload={"panel_id":panel["id"]},preview={"safe_to_apply":True},status="pending",requested_by=user.id)
    session.add(job); await session.commit(); return {"job_id":str(job.id)}

@router.get("/discord/guilds/{guild_id}/plugins/role-menu/jobs/{job_id}")
async def job_status(guild_id:int,job_id:UUID,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_module(session,user,guild_id,"plugins"); job=await session.get(DiscordStructureChange,job_id)
    if not job or job.guild_id!=guild_id or job.object_type!="role_menu_panel": raise HTTPException(404,"Publication job not found")
    return {"status":job.status,"error":job.result_message,"message_id":((job.payload or {}).get("_result") or {}).get("message_id")}

@internal_router.get("/guilds/{guild_id}/configuration")
async def internal_configuration(guild_id:int,session:AsyncSession=Depends(get_db_session)): return await settings(session,guild_id)

@internal_router.post("/panel")
async def save_panel_result(payload:PanelResult,session:AsyncSession=Depends(get_db_session)):
    item=await installation(session,payload.guild_id)
    if not item: raise HTTPException(404,"Role Menu is not installed")
    rows=panels(item.configuration); panel=next((x for x in rows if x["id"]==payload.panel_id),None)
    if not panel or panel.get("channel_id")!=payload.channel_id: raise HTTPException(422,"Panel channel does not match")
    panel["message_id"]=payload.message_id; item.configuration={**(item.configuration or {}),"panels":rows}; await session.commit(); return {"ok":True}
