from __future__ import annotations
import json
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import User
from app.models.media_assets import MediaAsset
from app.services.global_access import GlobalAccessService
from app.services.media_assets import MediaAssetStorage

router = APIRouter(tags=["Media Assets"])
storage = MediaAssetStorage()
ASSET_TYPES = {"background", "character", "logo", "icon", "frame", "effect", "badge", "sticker", "font"}

class AssetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    game_library_id: UUID | None = None
    tags: list[str] | None = None
    is_active: bool | None = None
    metadata: dict | None = None

def require_superadmin(user: User) -> None:
    GlobalAccessService.require_superadmin(user)

def serialize(row: MediaAsset) -> dict:
    return {
        "id": str(row.id), "key": row.key, "name": row.name,
        "description": row.description, "asset_type": row.asset_type,
        "game_library_id": str(row.game_library_id) if row.game_library_id else None,
        "url": f"/api/v1/platform/media-assets/{row.id}/file",
        "preview_url": f"/api/v1/platform/media-assets/{row.id}/preview",
        "mime_type": row.mime_type, "file_size": row.file_size,
        "width": row.width, "height": row.height,
        "tags": row.tags or [], "metadata": row.metadata or {},
        "is_active": row.is_active, "created_at": row.created_at,
    }

@router.get("/platform/media-assets")
async def list_assets(asset_type: str | None = None, game_library_id: UUID | None = None,
                      current_user: User = Depends(get_current_user),
                      session: AsyncSession = Depends(get_db_session)):
    require_superadmin(current_user)
    query = select(MediaAsset).order_by(MediaAsset.asset_type, MediaAsset.name)
    if asset_type:
        query = query.where(MediaAsset.asset_type == asset_type)
    if game_library_id:
        query = query.where(MediaAsset.game_library_id == game_library_id)
    rows = (await session.execute(query)).scalars().all()
    return {"items": [serialize(x) for x in rows], "types": sorted(ASSET_TYPES)}

@router.post("/platform/media-assets", status_code=201)
async def create_asset(
    key: str = Form(...), name: str = Form(...), asset_type: str = Form(...),
    description: str | None = Form(None), game_library_id: UUID | None = Form(None),
    tags_json: str = Form("[]"), metadata_json: str = Form("{}"),
    file: UploadFile = File(...), preview: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    require_superadmin(current_user)
    if asset_type not in ASSET_TYPES:
        raise HTTPException(422, "Unknown asset type.")
    safe_key = storage.safe_key(key)
    if await session.scalar(select(MediaAsset).where(MediaAsset.key == safe_key)):
        raise HTTPException(409, "Asset key already exists.")
    try:
        tags = json.loads(tags_json or "[]")
        metadata = json.loads(metadata_json or "{}")
    except json.JSONDecodeError:
        raise HTTPException(422, "Invalid JSON in tags or metadata.")

    row = MediaAsset(
        key=safe_key, name=name.strip(), description=description,
        asset_type=asset_type, game_library_id=game_library_id,
        file_path="", mime_type=file.content_type or "application/octet-stream",
        tags=tags if isinstance(tags, list) else [], metadata=metadata if isinstance(metadata, dict) else {},
        created_by_user_id=getattr(current_user, "id", None),
    )
    session.add(row)
    await session.flush()
    try:
        row.file_path, row.file_size, row.width, row.height = await storage.save(row.id, file)
        if preview is not None:
            row.preview_path, _, _, _ = await storage.save(row.id, preview, "preview")
        await session.commit()
        await session.refresh(row)
        return serialize(row)
    except Exception:
        await session.rollback()
        storage.delete(row.id)
        raise

@router.patch("/platform/media-assets/{asset_id}")
async def update_asset(asset_id: UUID, payload: AssetUpdate,
                       current_user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_db_session)):
    require_superadmin(current_user)
    row = await session.get(MediaAsset, asset_id)
    if not row:
        raise HTTPException(404, "Asset not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return serialize(row)

@router.delete("/platform/media-assets/{asset_id}", status_code=204)
async def delete_asset(asset_id: UUID, current_user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_db_session)):
    require_superadmin(current_user)
    row = await session.get(MediaAsset, asset_id)
    if not row:
        raise HTTPException(404, "Asset not found.")
    await session.delete(row)
    await session.commit()
    storage.delete(asset_id)
    return Response(status_code=204)

def file_response(path_value: str | None):
    if not path_value:
        raise HTTPException(404, "Asset not found.")
    path = Path(path_value)
    if not path.is_file():
        raise HTTPException(404, "Asset file not found.")
    mime = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif",
        ".ttf": "font/ttf", ".otf": "font/otf",
    }.get(path.suffix.lower(), "application/octet-stream")
    return Response(content=path.read_bytes(), media_type=mime)

@router.get("/platform/media-assets/{asset_id}/file")
async def asset_file(asset_id: UUID, _: User = Depends(get_current_user),
                     session: AsyncSession = Depends(get_db_session)):
    row = await session.get(MediaAsset, asset_id)
    if not row:
        raise HTTPException(404, "Asset not found.")
    return file_response(row.file_path)

@router.get("/platform/media-assets/{asset_id}/preview")
async def asset_preview(asset_id: UUID, _: User = Depends(get_current_user),
                        session: AsyncSession = Depends(get_db_session)):
    row = await session.get(MediaAsset, asset_id)
    if not row:
        raise HTTPException(404, "Asset not found.")
    return file_response(row.preview_path or row.file_path)
