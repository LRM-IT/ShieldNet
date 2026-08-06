from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import User
from app.models.template_bank import MediaTemplate, TemplateBankSettings
from app.services.global_access import GlobalAccessService
from app.services.template_bank import TemplateStorage

router = APIRouter(tags=["Template Bank"])
storage = TemplateStorage()
CATEGORIES = {"voting", "ranks"}


class SettingsUpdate(BaseModel):
    default_qr_url: HttpUrl
    default_qr_caption: str = Field(min_length=1, max_length=255)
    allow_guild_qr_override: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = None
    subcategory: str | None = Field(default=None, max_length=80)
    is_active: bool | None = None
    is_default: bool | None = None
    manifest: dict | None = None


def require_superadmin(user: User):
    GlobalAccessService.require_superadmin(user)


def serialize(row: MediaTemplate):
    return {
        "id": str(row.id), "key": row.key, "name": row.name,
        "description": row.description, "category": row.category,
        "subcategory": row.subcategory, "version": row.version,
        "is_active": row.is_active, "is_default": row.is_default,
        "canvas_width": row.canvas_width, "canvas_height": row.canvas_height,
        "background_url": f"/api/v1/platform/template-bank/templates/{row.id}/background",
        "preview_url": f"/api/v1/platform/template-bank/templates/{row.id}/preview",
        "manifest": row.manifest or {}, "created_at": row.created_at, "updated_at": row.updated_at,
    }


async def ensure_settings(session):
    row = await session.get(TemplateBankSettings, 1)
    if row is None:
        row = TemplateBankSettings(id=1)
        session.add(row)
        await session.flush()
    return row


@router.get("/platform/template-bank/settings")
async def read_settings(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    require_superadmin(current_user)
    row = await ensure_settings(session)
    await session.commit()
    return {"default_qr_url": row.default_qr_url, "default_qr_caption": row.default_qr_caption, "allow_guild_qr_override": row.allow_guild_qr_override}


@router.put("/platform/template-bank/settings")
async def write_settings(payload: SettingsUpdate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    require_superadmin(current_user)
    row = await ensure_settings(session)
    row.default_qr_url = str(payload.default_qr_url)
    row.default_qr_caption = payload.default_qr_caption.strip()
    row.allow_guild_qr_override = payload.allow_guild_qr_override
    await session.commit()
    return {"default_qr_url": row.default_qr_url, "default_qr_caption": row.default_qr_caption, "allow_guild_qr_override": row.allow_guild_qr_override}


@router.get("/platform/template-bank/templates")
async def list_templates(category: str | None = None, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    require_superadmin(current_user)
    query = select(MediaTemplate).order_by(MediaTemplate.category, MediaTemplate.name)
    if category:
        query = query.where(MediaTemplate.category == category)
    rows = (await session.execute(query)).scalars().all()
    return {"items": [serialize(x) for x in rows], "categories": sorted(CATEGORIES)}


@router.get("/templates")
async def plugin_templates(category: str, _: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    if category not in CATEGORIES:
        raise HTTPException(422, "Unknown template category.")
    rows = (await session.execute(select(MediaTemplate).where(MediaTemplate.category == category, MediaTemplate.is_active.is_(True)).order_by(MediaTemplate.is_default.desc(), MediaTemplate.name))).scalars().all()
    return {"items": [serialize(x) for x in rows]}


@router.post("/platform/template-bank/templates", status_code=status.HTTP_201_CREATED)
async def create_template(
    key: str = Form(...), name: str = Form(...), category: str = Form(...), subcategory: str | None = Form(None),
    description: str | None = Form(None), canvas_width: int = Form(...), canvas_height: int = Form(...), manifest_json: str = Form("{}"),
    background: UploadFile = File(...), preview: UploadFile | None = File(None), current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    require_superadmin(current_user)
    if category not in CATEGORIES:
        raise HTTPException(422, "Category must be voting or ranks.")
    safe_key = storage.safe_key(key)
    if await session.scalar(select(MediaTemplate).where(MediaTemplate.key == safe_key)):
        raise HTTPException(409, "Template key already exists.")
    if not (320 <= canvas_width <= 4096 and 320 <= canvas_height <= 4096):
        raise HTTPException(422, "Canvas dimensions must be between 320 and 4096.")
    row = MediaTemplate(key=safe_key, name=name.strip(), category=category, subcategory=subcategory, description=description,
        canvas_width=canvas_width, canvas_height=canvas_height, background_path="",
        manifest=storage.validate_manifest(manifest_json, canvas_width, canvas_height), created_by_user_id=getattr(current_user, "id", None))
    session.add(row)
    await session.flush()
    try:
        row.background_path = await storage.save_image(row.id, row.version, "background", background)
        if preview:
            row.preview_path = await storage.save_image(row.id, row.version, "preview", preview)
        await session.commit(); await session.refresh(row)
        return serialize(row)
    except Exception:
        await session.rollback(); storage.delete_template(row.id); raise


@router.patch("/platform/template-bank/templates/{template_id}")
async def update_template(template_id: UUID, payload: TemplateUpdate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    require_superadmin(current_user)
    row = await session.get(MediaTemplate, template_id)
    if not row:
        raise HTTPException(404, "Template not found.")
    values = payload.model_dump(exclude_unset=True)
    if values.get("is_default"):
        await session.execute(update(MediaTemplate).where(MediaTemplate.category == row.category).values(is_default=False))
    for key, value in values.items():
        setattr(row, key, value)
    await session.commit(); await session.refresh(row)
    return serialize(row)


@router.delete("/platform/template-bank/templates/{template_id}", status_code=204)
async def delete_template(template_id: UUID, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    require_superadmin(current_user)
    row = await session.get(MediaTemplate, template_id)
    if not row:
        raise HTTPException(404, "Template not found.")
    await session.delete(row); await session.commit(); storage.delete_template(template_id)
    return Response(status_code=204)


def asset(path_value: str | None):
    if not path_value or not Path(path_value).is_file():
        raise HTTPException(404, "Asset not found.")
    path = Path(path_value)
    media = {".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".webp":"image/webp"}.get(path.suffix.lower())
    return Response(content=path.read_bytes(), media_type=media)


@router.get("/platform/template-bank/templates/{template_id}/background")
async def background(template_id: UUID, _: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    row = await session.get(MediaTemplate, template_id)
    if not row: raise HTTPException(404, "Template not found.")
    return asset(row.background_path)


@router.get("/platform/template-bank/templates/{template_id}/preview")
async def preview(template_id: UUID, _: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    row = await session.get(MediaTemplate, template_id)
    if not row: raise HTTPException(404, "Template not found.")
    return asset(row.preview_path or row.background_path)
