from __future__ import annotations
import re
import io
from pathlib import Path
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.models.template_bank import GameLibrary, MediaTemplate, TemplateBankSettings
from app.services.global_access import GlobalAccessService

router=APIRouter(tags=["Template Bank"])
CATEGORIES={"voting","ranks"}
VOTING_TEMPLATE_ROOT = Path("/var/lib/shieldnet/templates/voting")
VOTING_IMAGE_TYPES = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
VOTING_MAX_BYTES = 20 * 1024 * 1024

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
            "preview_url":(f"/api/v1/platform/voting-templates/{x.id}/image" if x.category=="voting"
                           else f"/api/v1/platform/template-bank/templates/{x.id}/preview"),
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


def voting_manifest(width:int, height:int, title:dict, score:dict) -> dict:
    layers=[]
    for marker, field, default_size in ((title,"{{TITLE}}",max(24,width//25)),
                                         (score,"{{RESULT_SCORES}}",max(18,width//38))):
        x=int(marker.get("x",0)); y=int(marker.get("y",0))
        w=int(marker.get("width",0)); h=int(marker.get("height",0))
        if x<0 or y<0 or w<20 or h<20 or x+w>width or y+h>height:
            raise HTTPException(422,"Title and score markers must fit inside the image.")
        color=str(marker.get("color") or "#ffffff")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}",color):
            raise HTTPException(422,"Marker color must be a six-digit hex color.")
        align=marker.get("align","left")
        if align not in {"left","center","right"}:
            raise HTTPException(422,"Invalid marker alignment.")
        layers.append({"type":"text","variable":field,"x":x,"y":y,
                       "width":w,"height":h,"fontSize":max(12,min(160,int(marker.get("fontSize",default_size)))),
                       "fontWeight":"700","color":color,"align":align,"visible":True})
    return {"canvas":{"width":width,"height":height},"layers":layers}


@router.get("/discord/guilds/{guild_id}/plugins/voting/templates")
async def voting_templates(guild_id:int, current_user:User=Depends(get_current_user),
                           session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,current_user,guild_id)
    rows=(await session.execute(select(MediaTemplate).where(MediaTemplate.category=="voting",
          MediaTemplate.is_active.is_(True)).order_by(MediaTemplate.name))).scalars().all()
    return {"items":[template_out(row) for row in rows]}


@router.get("/platform/voting-templates")
async def list_voting_templates(current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    rows=(await session.execute(select(MediaTemplate).where(MediaTemplate.category=="voting")
                        .order_by(MediaTemplate.name))).scalars().all()
    return {"items":[template_out(row) for row in rows]}


@router.post("/platform/voting-templates",status_code=201)
async def create_voting_template(name:str=Form(...), title_json:str=Form(...), score_json:str=Form(...),
    file:UploadFile=File(...), current_user:User=Depends(get_current_user),
    session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    import json
    if not 2<=len(name.strip())<=180:
        raise HTTPException(422,"Template name must contain 2-180 characters.")
    if file.content_type not in VOTING_IMAGE_TYPES:
        raise HTTPException(422,"Upload a PNG, JPEG or WebP image.")
    raw=await file.read(VOTING_MAX_BYTES+1)
    if len(raw)>VOTING_MAX_BYTES:
        raise HTTPException(413,"Template image exceeds 20 MB.")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            width,height=image.size
            if image.format!=VOTING_IMAGE_TYPES[file.content_type] or width<320 or height<240 or width*height>20_000_000:
                raise ValueError("Unsupported image dimensions or format")
        manifest=voting_manifest(width,height,json.loads(title_json),json.loads(score_json))
    except (ValueError,TypeError,UnidentifiedImageError,KeyError) as exc:
        raise HTTPException(422,f"Invalid template image or markers: {exc}") from exc
    key=f"voting-{uuid4().hex}"
    row=MediaTemplate(key=key,name=name.strip(),category="voting",canvas_width=width,
        canvas_height=height,background_path="",manifest=manifest,
        created_by_user_id=current_user.id,is_active=True,is_default=False)
    session.add(row)
    await session.flush()
    path=VOTING_TEMPLATE_ROOT/f"{row.id}.{file.content_type.split('/')[-1].replace('jpeg','jpg')}"
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw)
        row.background_path=str(path)
        await session.commit(); await session.refresh(row)
    except Exception:
        await session.rollback(); path.unlink(missing_ok=True); raise
    return template_out(row)


@router.put("/platform/voting-templates/{template_id}")
async def update_voting_template(template_id:UUID,payload:dict,current_user:User=Depends(get_current_user),
    session:AsyncSession=Depends(get_db_session)):
    require_superadmin(current_user)
    row=await session.get(MediaTemplate,template_id)
    if not row or row.category!="voting": raise HTTPException(404,"Voting template not found.")
    if "name" in payload:
        name=str(payload["name"]).strip()
        if not 2<=len(name)<=180: raise HTTPException(422,"Invalid template name.")
        row.name=name
    if "title" in payload or "score" in payload:
        existing=row.manifest.get("layers",[])
        title=payload.get("title") or (existing[0] if len(existing)>0 else {})
        score=payload.get("score") or (existing[1] if len(existing)>1 else {})
        row.manifest=voting_manifest(row.canvas_width,row.canvas_height,title,score)
    if "is_active" in payload: row.is_active=bool(payload["is_active"])
    if payload.get("is_default"):
        await session.execute(update(MediaTemplate).where(MediaTemplate.category=="voting").values(is_default=False))
        row.is_default=True
    elif "is_default" in payload: row.is_default=False
    await session.commit(); await session.refresh(row)
    return template_out(row)


@router.get("/platform/voting-templates/{template_id}/image")
async def voting_template_image(template_id:UUID,_:User=Depends(get_current_user),
    session:AsyncSession=Depends(get_db_session)):
    row=await session.get(MediaTemplate,template_id)
    if not row or row.category!="voting": raise HTTPException(404,"Voting template not found.")
    path=Path(row.background_path)
    if not path.is_file(): raise HTTPException(404,"Template image not found.")
    media={".png":"image/png",".jpg":"image/jpeg",".webp":"image/webp"}.get(path.suffix.lower())
    return Response(path.read_bytes(),media_type=media or "application/octet-stream")
