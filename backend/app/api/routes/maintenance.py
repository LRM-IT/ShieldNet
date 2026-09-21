from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.core import User
from app.services.settings import SettingsService

router = APIRouter(tags=["Platform maintenance"])
MODULE = "platform_maintenance"
KEY = "mode"
Mode = Literal["normal", "maintenance", "testing"]


class MaintenanceUpdate(BaseModel):
    mode: Mode


async def current_mode(session: AsyncSession) -> Mode:
    value = await SettingsService(session).get(0, MODULE, KEY, "normal")
    return value if value in {"normal", "maintenance", "testing"} else "normal"


@router.get("/public/maintenance")
async def public_maintenance(session: AsyncSession = Depends(get_db_session)):
    return {"mode": await current_mode(session)}


@router.get("/platform/maintenance")
async def get_maintenance(
    _: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
):
    return {"mode": await current_mode(session)}


@router.put("/platform/maintenance")
async def update_maintenance(
    payload: MaintenanceUpdate,
    user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_db_session),
):
    await SettingsService(session).set(
        guild_id=0,
        module=MODULE,
        key=KEY,
        value=payload.mode,
        updated_by=user.id,
    )
    return {"mode": payload.mode}
