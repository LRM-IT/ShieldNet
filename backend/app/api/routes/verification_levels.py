from __future__ import annotations

import base64, io, json, re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.verification import VerificationLevel, VerificationLevelSubmission
from app.services.ai_runtime import AIRuntimeService

router = APIRouter(tags=["Verification levels"])
internal_router = APIRouter(prefix="/internal/verification-levels", tags=["Internal verification levels"], dependencies=[Depends(verify_internal_service_token)])
ROOT = Path("/var/lib/shieldnet/templates/verification")
ALLOWED_HOSTS = {"cdn.discordapp.com", "media.discordapp.net", "images-ext-1.discordapp.net", "images-ext-2.discordapp.net"}

class CriterionInput(BaseModel):
    label: str = Field(min_length=1,max_length=80)
    expected_text: str = Field(min_length=1,max_length=500)
    values: list[str] = Field(default_factory=list,max_length=20)
    role_ids: list[int] = Field(default_factory=list,max_length=20)
    @field_validator("values")
    @classmethod
    def clean_values(cls,value):
        cleaned=list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
        if any(len(item)>100 for item in cleaned): raise ValueError("Recognition values must be at most 100 characters")
        return cleaned

class LevelInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = False
    channel_id: int | None = None
    expected_text: str = Field(default="", max_length=500)
    role_ids: list[int] = Field(default_factory=list, max_length=20)
    criteria: list[CriterionInput] = Field(default_factory=list,max_length=20)
    marker: dict = Field(default_factory=lambda: {"x":0,"y":0,"width":1,"height":1})
    @field_validator("marker")
    @classmethod
    def marker_bounds(cls, value):
        normalized = {key: float(value.get(key, default)) for key, default in (("x",0),("y",0),("width",1),("height",1))}
        if not (0 <= normalized["x"] < 1 and 0 <= normalized["y"] < 1 and 0 < normalized["width"] <= 1 and 0 < normalized["height"] <= 1 and normalized["x"]+normalized["width"] <= 1 and normalized["y"]+normalized["height"] <= 1):
            raise ValueError("Marker must stay inside the image")
        return normalized

class SubmissionInput(BaseModel):
    guild_id: int; level_id: UUID; discord_user_id: int; discord_message_id: int; image_url: str

def serialize(row: VerificationLevel) -> dict:
    criteria=row.criteria or ([{"label":"Основна ознака","expected_text":row.expected_text,"values":[row.expected_text],"role_ids":row.role_ids}] if row.expected_text else [])
    criteria=[{**item,"values":item.get("values") or [item.get("expected_text","")]} for item in criteria]
    return {"id":str(row.id),"name":row.name,"enabled":row.enabled,"channel_id":str(row.channel_id) if row.channel_id else None,
            "expected_text":row.expected_text,"role_ids":[str(x) for x in row.role_ids],"marker":row.marker,
            "criteria":[{**item,"role_ids":[str(x) for x in item.get("role_ids",[])]} for item in criteria],
            "has_template":bool(row.template_path),"template_url":f"/api/v1/discord/guilds/{row.guild_id}/verification/levels/{row.id}/template" if row.template_path else None}

@router.get("/discord/guilds/{guild_id}/verification/levels")
async def levels(guild_id:int,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,user,guild_id)
    rows=(await session.execute(select(VerificationLevel).where(VerificationLevel.guild_id==guild_id).order_by(VerificationLevel.position,VerificationLevel.created_at))).scalars().all()
    return [serialize(row) for row in rows]

@router.post("/discord/guilds/{guild_id}/verification/levels")
async def create_level(guild_id:int,payload:LevelInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,user,guild_id)
    if payload.enabled: raise HTTPException(422,"Upload a template before enabling the level")
    row=VerificationLevel(guild_id=guild_id,**payload.model_dump(),position=(await session.scalar(select(VerificationLevel).where(VerificationLevel.guild_id==guild_id).with_for_update()) is not None)+1)
    session.add(row); await session.commit(); await session.refresh(row); return serialize(row)

@router.put("/discord/guilds/{guild_id}/verification/levels/{level_id}")
async def update_level(guild_id:int,level_id:UUID,payload:LevelInput,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,user,guild_id); row=await session.get(VerificationLevel,level_id)
    if not row or row.guild_id!=guild_id: raise HTTPException(404,"Verification level not found")
    if payload.enabled and (not payload.channel_id or not payload.criteria or not row.template_path):
        raise HTTPException(422,"Select a channel, upload a template and add at least one recognition rule")
    if payload.channel_id:
        conflict=await session.scalar(select(VerificationLevel).where(VerificationLevel.guild_id==guild_id,VerificationLevel.channel_id==payload.channel_id,VerificationLevel.id!=level_id))
        if conflict: raise HTTPException(422,"Each verification level needs its own channel or thread")
    for key,value in payload.model_dump().items(): setattr(row,key,value)
    await session.commit(); return serialize(row)

@router.delete("/discord/guilds/{guild_id}/verification/levels/{level_id}",status_code=204)
async def delete_level(guild_id:int,level_id:UUID,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,user,guild_id); row=await session.get(VerificationLevel,level_id)
    if not row or row.guild_id!=guild_id: raise HTTPException(404,"Verification level not found")
    if row.template_path: Path(row.template_path).unlink(missing_ok=True)
    await session.delete(row); await session.commit()

@router.post("/discord/guilds/{guild_id}/verification/levels/{level_id}/template")
async def upload_template(guild_id:int,level_id:UUID,file:UploadFile=File(...),marker_json:str=Form("{}"),user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,user,guild_id); row=await session.get(VerificationLevel,level_id)
    if not row or row.guild_id!=guild_id: raise HTTPException(404,"Verification level not found")
    content=await file.read(10*1024*1024+1)
    if len(content)>10*1024*1024 or file.content_type not in {"image/png","image/jpeg","image/webp"}: raise HTTPException(422,"Upload PNG, JPEG or WebP up to 10 MB")
    try: Image.open(io.BytesIO(content)).verify(); marker=LevelInput.marker_bounds(json.loads(marker_json))
    except Exception as exc: raise HTTPException(422,"Invalid image or marker") from exc
    folder=ROOT/str(guild_id); folder.mkdir(parents=True,exist_ok=True); path=folder/f"{level_id}.img"; path.write_bytes(content)
    row.template_path=str(path); row.template_mime=file.content_type; row.marker=marker; await session.commit(); return serialize(row)

@router.get("/discord/guilds/{guild_id}/verification/levels/{level_id}/template")
async def template(guild_id:int,level_id:UUID,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    from fastapi.responses import Response
    await require_guild_management(session,user,guild_id); row=await session.get(VerificationLevel,level_id)
    if not row or row.guild_id!=guild_id or not row.template_path: raise HTTPException(404,"Template not found")
    return Response(Path(row.template_path).read_bytes(),media_type=row.template_mime)

@internal_router.get("/guilds/{guild_id}")
async def internal_levels(guild_id:int,session:AsyncSession=Depends(get_db_session)):
    rows=(await session.execute(select(VerificationLevel).where(VerificationLevel.guild_id==guild_id,VerificationLevel.enabled.is_(True)))).scalars().all()
    return {"levels":[serialize(row) for row in rows]}

def data_url(raw:bytes,mime:str,marker:dict)->str:
    image=Image.open(io.BytesIO(raw)).convert("RGB"); w,h=image.size
    box=(int(marker["x"]*w),int(marker["y"]*h),int((marker["x"]+marker["width"])*w),int((marker["y"]+marker["height"])*h))
    out=io.BytesIO(); image.crop(box).save(out,"JPEG",quality=90)
    return "data:image/jpeg;base64,"+base64.b64encode(out.getvalue()).decode()

@internal_router.post("/analyze")
async def analyze(payload:SubmissionInput,session:AsyncSession=Depends(get_db_session)):
    row=await session.get(VerificationLevel,payload.level_id)
    if not row or row.guild_id!=payload.guild_id or not row.enabled or not row.template_path: raise HTTPException(409,"Verification level is unavailable")
    host=(urlparse(payload.image_url).hostname or "").lower()
    if host not in ALLOWED_HOSTS: raise HTTPException(422,"Only Discord image attachments are accepted")
    async with httpx.AsyncClient(timeout=30,follow_redirects=True) as client:
        response=await client.get(payload.image_url); response.raise_for_status(); submitted=response.content
    if len(submitted)>10*1024*1024: raise HTTPException(422,"Image is too large")
    item=VerificationLevelSubmission(level_id=row.id,guild_id=row.guild_id,discord_user_id=payload.discord_user_id,discord_message_id=payload.discord_message_id,image_url=payload.image_url)
    session.add(item); await session.flush()
    criteria=row.criteria or ([{"label":"Основна ознака","expected_text":row.expected_text,"values":[row.expected_text],"role_ids":row.role_ids}] if row.expected_text else [])
    criteria=[{**item,"values":item.get("values") or [item.get("expected_text","")]} for item in criteria]
    checks="\n".join(f"{index}: {item['label']} — confirm if ANY of these values is visible: {item['values']!r}" for index,item in enumerate(criteria))
    prompt=("Compare image 1 (owner reference marker) with image 2 (member profile marker). Check every rule independently:\n"+checks+
            "\nReturn strict JSON: {\"matched_indices\":[0],\"detected_text\":\"...\",\"confidence\":0.0,\"reason\":\"...\"}. "
            "matched_indices must contain only rules visibly confirmed in image 2.")
    try:
        _,result=await AIRuntimeService(session).execute(guild_id=row.guild_id,module_key="verification",capability="recognition",input_text=prompt,
            image_data_urls=[data_url(Path(row.template_path).read_bytes(),row.template_mime or "image/png",row.marker),data_url(submitted,response.headers.get("content-type","image/jpeg"),row.marker)],max_output_tokens=500)
        parsed=json.loads(re.sub(r"^```(?:json)?|```$","",result.text.strip(),flags=re.I).strip())
        indices=sorted({int(index) for index in parsed.get("matched_indices",[]) if str(index).isdigit() and 0<=int(index)<len(criteria)})
        matched=bool(indices); roles=list(dict.fromkeys(role for index in indices for role in criteria[index].get("role_ids",[])))
        item.status="verified" if matched else "rejected"; item.matched=matched; item.detected_text=str(parsed.get("detected_text") or ""); item.ai_result=parsed; item.result_message=str(parsed.get("reason") or ""); item.completed_at=datetime.now(UTC)
        await session.commit(); return {"submission_id":str(item.id),"matched":matched,"matched_criteria":[criteria[index]["label"] for index in indices],"role_ids":[str(x) for x in roles],"detected_text":item.detected_text,"reason":item.result_message,"level_name":row.name}
    except Exception as exc:
        item.status="failed"; item.result_message=str(exc)[:2000]; item.completed_at=datetime.now(UTC); await session.commit(); raise HTTPException(502,"AI image verification failed") from exc
