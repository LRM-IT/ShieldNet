from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import User
from app.models.global_languages import GlobalLanguage
from app.services.global_access import GlobalAccessService

router = APIRouter(tags=["Global Languages"])


class LanguageCreate(BaseModel):
    code: str = Field(min_length=2, max_length=16)
    name: str = Field(min_length=1, max_length=120)
    native_name: str = Field(min_length=1, max_length=120)
    flag: str | None = Field(default=None, max_length=16)
    locale: str | None = Field(default=None, max_length=32)
    is_active: bool = True
    sort_order: int = Field(default=100, ge=0, le=10000)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().lower().replace("_", "-")
        if not all(part.isalnum() for part in value.split("-")):
            raise ValueError("Language code must contain letters, digits or hyphens")
        return value


class LanguageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    native_name: str | None = Field(default=None, min_length=1, max_length=120)
    flag: str | None = Field(default=None, max_length=16)
    locale: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10000)


def require_superadmin(user: User) -> None:
    GlobalAccessService.require_superadmin(user)


def serialize(item: GlobalLanguage) -> dict:
    return {
        "id": item.id,
        "code": item.code,
        "name": item.name,
        "native_name": item.native_name,
        "flag": item.flag,
        "locale": item.locale,
        "is_active": item.is_active,
        "sort_order": item.sort_order,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("/languages")
async def list_active_languages(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    rows = (
        await session.execute(
            select(GlobalLanguage)
            .where(GlobalLanguage.is_active.is_(True))
            .order_by(GlobalLanguage.sort_order, GlobalLanguage.name)
        )
    ).scalars().all()
    return [serialize(item) for item in rows]


@router.get("/platform/languages")
async def list_all_languages(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    require_superadmin(current_user)
    rows = (
        await session.execute(
            select(GlobalLanguage).order_by(
                GlobalLanguage.sort_order,
                GlobalLanguage.name,
            )
        )
    ).scalars().all()
    return [serialize(item) for item in rows]


@router.post("/platform/languages", status_code=status.HTTP_201_CREATED)
async def create_language(
    payload: LanguageCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    require_superadmin(current_user)
    existing = await session.scalar(
        select(GlobalLanguage).where(GlobalLanguage.code == payload.code)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Language code already exists")
    item = GlobalLanguage(**payload.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return serialize(item)


@router.patch("/platform/languages/{language_id}")
async def update_language(
    language_id: int,
    payload: LanguageUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    require_superadmin(current_user)
    item = await session.get(GlobalLanguage, language_id)
    if not item:
        raise HTTPException(status_code=404, detail="Language not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return serialize(item)


@router.delete("/platform/languages/{language_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_language(
    language_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    require_superadmin(current_user)
    item = await session.get(GlobalLanguage, language_id)
    if not item:
        raise HTTPException(status_code=404, detail="Language not found")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
