from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import GlobalRole, User
from app.models.platform_ai import PlatformAIProvider, PlatformAISettings
from app.schemas.ai_gateway import AIProviderCreate, AIProviderTestResponse, AIProviderUpdate
from app.services.ai_gateway import AIGatewayService
from app.services.ai_secrets import AISecretService
from app.services.global_access import GlobalAccessService

router = APIRouter(prefix="/platform/ai", tags=["Platform AI Center"])


class PlatformSettingsPayload(BaseModel):
    defaults: dict = Field(default_factory=dict)
    limits: dict = Field(default_factory=dict)
    emergency_stop: bool = False


def require_platform_ai_access(user: User) -> None:
    GlobalAccessService.require_any(user, [GlobalRole.SUPERADMIN, GlobalRole.ADMIN])


def serialize_provider(row: PlatformAIProvider) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "provider_type": row.provider_type,
        "api_base_url": row.api_base_url,
        "key_hint": row.key_hint,
        "organization_id": row.organization_id,
        "project_id": row.project_id,
        "default_model": row.default_model,
        "enabled": row.enabled,
        "priority": row.priority,
        "timeout_seconds": row.timeout_seconds,
        "max_retries": row.max_retries,
        "capabilities": row.capabilities or [],
        "settings": row.settings or {},
        "last_health_status": row.last_health_status,
        "last_health_latency_ms": row.last_health_latency_ms,
        "last_health_check_at": row.last_health_check_at.isoformat() if row.last_health_check_at else None,
        "last_error": row.last_error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def get_provider(session: AsyncSession, provider_id: UUID) -> PlatformAIProvider:
    row = await session.get(PlatformAIProvider, provider_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Platform AI provider not found")
    return row


@router.get("/providers")
async def list_providers(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    require_platform_ai_access(current_user)
    rows = (
        await session.execute(
            select(PlatformAIProvider).order_by(
                PlatformAIProvider.priority,
                PlatformAIProvider.name,
            )
        )
    ).scalars().all()
    return [serialize_provider(row) for row in rows]


@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: AIProviderCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    require_platform_ai_access(current_user)

    duplicate = (
        await session.execute(
            select(PlatformAIProvider).where(PlatformAIProvider.name == payload.name)
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="A platform provider with this name already exists")

    row = PlatformAIProvider(
        name=payload.name,
        provider_type=payload.provider_type,
        api_base_url=payload.api_base_url,
        encrypted_api_key=AISecretService.encrypt(payload.api_key),
        key_hint=AISecretService.hint(payload.api_key),
        organization_id=payload.organization_id,
        project_id=payload.project_id,
        default_model=payload.default_model,
        enabled=payload.enabled,
        priority=payload.priority,
        timeout_seconds=payload.timeout_seconds,
        max_retries=payload.max_retries,
        capabilities=payload.capabilities,
        settings=payload.settings,
        created_by=current_user.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return serialize_provider(row)


@router.patch("/providers/{provider_id}")
async def update_provider(
    provider_id: UUID,
    payload: AIProviderUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    require_platform_ai_access(current_user)
    row = await get_provider(session, provider_id)
    values = payload.model_dump(exclude_unset=True)
    api_key = values.pop("api_key", None)
    if api_key:
        row.encrypted_api_key = AISecretService.encrypt(api_key)
        row.key_hint = AISecretService.hint(api_key)
    for key, value in values.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return serialize_provider(row)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    require_platform_ai_access(current_user)
    row = await get_provider(session, provider_id)
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)


@router.post("/providers/{provider_id}/test", response_model=AIProviderTestResponse)
async def test_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AIProviderTestResponse:
    require_platform_ai_access(current_user)
    row = await get_provider(session, provider_id)
    try:
        health, latency, detail = await AIGatewayService(session).test_provider(row)
    except Exception as exc:
        health, latency, detail = "error", 0, str(exc)[:500]
    row.last_health_status = health
    row.last_health_latency_ms = latency
    row.last_health_check_at = datetime.now(timezone.utc)
    row.last_error = None if health == "connected" else detail
    await session.commit()
    return AIProviderTestResponse(
        provider_id=row.id,
        status=health,
        latency_ms=latency,
        detail=detail,
    )


@router.get("/settings")
async def get_settings(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    require_platform_ai_access(current_user)
    row = await session.get(PlatformAISettings, 1)
    if row is None:
        row = PlatformAISettings(id=1)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return {
        "defaults": row.defaults or {},
        "limits": row.limits or {},
        "emergency_stop": row.emergency_stop,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.put("/settings")
async def save_settings(
    payload: PlatformSettingsPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    require_platform_ai_access(current_user)
    row = await session.get(PlatformAISettings, 1)
    if row is None:
        row = PlatformAISettings(id=1)
        session.add(row)
    row.defaults = payload.defaults
    row.limits = payload.limits
    row.emergency_stop = payload.emergency_stop
    row.updated_by = current_user.id
    await session.commit()
    await session.refresh(row)
    return {
        "defaults": row.defaults or {},
        "limits": row.limits or {},
        "emergency_stop": row.emergency_stop,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
