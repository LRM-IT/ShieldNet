from __future__ import annotations
import re
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import User
from app.models.template_bank import GameLibrary, MediaTemplate, TemplateBankSettings
from app.services.global_access import GlobalAccessService

router=APIRouter(tags=["Template Bank"])
CATEGORIES={"voting","ranks"}

class SettingsUpdate(BaseModel):
    default_qr_url:HttpUrl
    default_qr_caption:str=Field(min_length=1,max_length=255)
    allow_guild_qr_override:bool=False

class GameIn(BaseModel):
    key:str=Field(min_length=2,max_length=120)
    name:str=Field(min_length=2,max_length=180)
    description:str|None=None
    sort_order:int=Field(default=100,ge=0,le=10000)
    is_active:bool=True

class TemplateUpdate(BaseModel):
    name:str|None=Field(default=None,min_length=2,max_length=180)
    description:str|None=None
    game_library_id:UUID|None=None
    subcategory:str|None=Field(default=None,max_length=80)
    is_active:bool|None=None
    is_default:bool|None=None
    manifest:dict|None=None

def require_superadmin(user:User)->None:
    GlobalAccessService.require_superadmin(user)

def game_out(x:GameLibrary)->dict:
    return {"id":str(x.id),"key":x.key,"name":x.name,"description":x.description,"sort_order":x.sort_order,"is_active":x.is_active}

def template_out(x:MediaTemplate)->dict:
    return {"id":str(x.id),"key":x.key,"name":x.name,"description":x.description,"category":x.category,
            "subcategory":x.subcategory,"game_library_id":str(x.game_library_id) if x.game_library_id else None,
            "version":x.version,"is_active":x.is_active,"is_default":x.is_default,
            "canvas_width":x.canvas_width,"canvas_height":x.canvas_height,
            "preview_url":f"/api/v1/platform/template-bank/templates/{x.id}/preview",
            "manifest":x.manifest or {}}

async def settings_row(session:AsyncSession)->TemplateBankSettings:
    row=await session.get(TemplateBankSettings,1)
    if row is None:
        row=TemplateBankSettings(id=1,default_qr_url="https://discord.lrm-it.com",
                                 default_qr_caption="Visit our website",allow_guild_qr_override=False)
        session.add(row); await session.flush()
    return row

@router.get("/platform/template-bank/settings")
async def get_settings(current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    row=await settings_row(session); await session.commit()
    return {"default_qr_url":row.default_qr_url,"default_qr_caption":row.default_qr_caption,
            "allow_guild_qr_override":row.allow_guild_qr_override}

@router.put("/platform/template-bank/settings")
async def put_settings(payload:SettingsUpdate,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    row=await settings_row(session)
    row.default_qr_url=str(payload.default_qr_url)
    row.default_qr_caption=payload.default_qr_caption.strip()
    row.allow_guild_qr_override=payload.allow_guild_qr_override
    await session.commit()
    return {"default_qr_url":row.default_qr_url,"default_qr_caption":row.default_qr_caption,
            "allow_guild_qr_override":row.allow_guild_qr_override}

@router.get("/platform/template-bank/games")
async def list_games(current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    rows=(await session.execute(select(GameLibrary).order_by(GameLibrary.sort_order,GameLibrary.name))).scalars().all()
    return {"items":[game_out(x) for x in rows]}

@router.post("/platform/template-bank/games",status_code=201)
async def create_game(payload:GameIn,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    key=re.sub(r"[^a-z0-9._-]+","-",payload.key.strip().lower()).strip("-")
    if await session.scalar(select(GameLibrary).where(GameLibrary.key==key)):
        raise HTTPException(409,"Game key already exists.")
    row=GameLibrary(**payload.model_dump(exclude={"key"}),key=key)
    session.add(row); await session.commit(); await session.refresh(row)
    return game_out(row)

@router.patch("/platform/template-bank/games/{game_id}")
async def update_game(game_id:UUID,payload:GameIn,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    row=await session.get(GameLibrary,game_id)
    if not row: raise HTTPException(404,"Game library not found.")
    for k,v in payload.model_dump().items():
        if k=="key": v=re.sub(r"[^a-z0-9._-]+","-",v.strip().lower()).strip("-")
        setattr(row,k,v)
    await session.commit(); await session.refresh(row); return game_out(row)

@router.delete("/platform/template-bank/games/{game_id}",status_code=204)
async def delete_game(game_id:UUID,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    row=await session.get(GameLibrary,game_id)
    if not row: raise HTTPException(404,"Game library not found.")
    await session.delete(row); await session.commit(); return Response(status_code=204)

@router.get("/platform/template-bank/templates")
async def list_templates(current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    rows=(await session.execute(select(MediaTemplate).order_by(MediaTemplate.category,MediaTemplate.name))).scalars().all()
    return {"items":[template_out(x) for x in rows],"categories":sorted(CATEGORIES)}

@router.patch("/platform/template-bank/templates/{template_id}")
async def update_template(template_id:UUID,payload:TemplateUpdate,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    row=await session.get(MediaTemplate,template_id)
    if not row: raise HTTPException(404,"Template not found.")
    values=payload.model_dump(exclude_unset=True)
    if values.get("is_default"):
        q=update(MediaTemplate).where(MediaTemplate.category==row.category,
                                     MediaTemplate.game_library_id==row.game_library_id).values(is_default=False)
        await session.execute(q)
    for k,v in values.items(): setattr(row,k,v)
    await session.commit(); await session.refresh(row); return template_out(row)
