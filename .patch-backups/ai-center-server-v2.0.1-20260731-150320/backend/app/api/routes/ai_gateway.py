from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.ai_gateway import GuildAIProvider, GuildAIRoute, GuildAIRouteTarget
from app.models.core import User
from app.schemas.ai_gateway import (
    AIProviderCreate, AIProviderResponse, AIProviderTestResponse, AIProviderUpdate,
    AIRouteResponse, AIRouteTargetResponse, AIRouteUpsert,
)
from app.services.ai_gateway import AIGatewayService
from app.services.ai_secrets import AISecretService

router = APIRouter(prefix="/discord/guilds/{guild_id}/ai", tags=["Server AI Center"])


def provider_response(row: GuildAIProvider) -> AIProviderResponse:
    return AIProviderResponse(
        id=row.id, guild_id=str(row.guild_id), name=row.name, provider_type=row.provider_type,
        api_base_url=row.api_base_url, key_hint=row.key_hint, organization_id=row.organization_id,
        project_id=row.project_id, default_model=row.default_model, enabled=row.enabled,
        priority=row.priority, timeout_seconds=row.timeout_seconds, max_retries=row.max_retries,
        capabilities=row.capabilities or [], settings=row.settings or {},
        last_health_status=row.last_health_status, last_health_latency_ms=row.last_health_latency_ms,
        last_health_check_at=row.last_health_check_at, last_error=row.last_error,
        consecutive_failures=row.consecutive_failures, circuit_open_until=row.circuit_open_until,
        created_at=row.created_at, updated_at=row.updated_at,
    )


async def route_response(session: AsyncSession, row: GuildAIRoute) -> AIRouteResponse:
    result = await session.execute(
        select(GuildAIRouteTarget)
        .where(GuildAIRouteTarget.route_id == row.id)
        .order_by(GuildAIRouteTarget.position)
    )
    targets = [
        AIRouteTargetResponse(
            id=x.id, provider_id=x.provider_id, position=x.position, model=x.model,
            timeout_seconds=x.timeout_seconds, retries=x.retries, enabled=x.enabled,
            configuration=x.configuration or {},
        )
        for x in result.scalars().all()
    ]
    return AIRouteResponse(
        id=row.id, guild_id=str(row.guild_id), capability=row.capability, enabled=row.enabled,
        max_total_attempts=row.max_total_attempts, failure_threshold=row.failure_threshold,
        cooldown_seconds=row.cooldown_seconds, configuration=row.configuration or {},
        targets=targets, created_at=row.created_at, updated_at=row.updated_at,
    )


@router.get("/providers", response_model=list[AIProviderResponse])
async def list_providers(guild_id: int, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    result = await session.execute(select(GuildAIProvider).where(GuildAIProvider.guild_id == guild_id).order_by(GuildAIProvider.priority, GuildAIProvider.name))
    return [provider_response(item) for item in result.scalars().all()]


@router.post("/providers", response_model=AIProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(guild_id: int, payload: AIProviderCreate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    row = GuildAIProvider(
        guild_id=guild_id, name=payload.name, provider_type=payload.provider_type,
        api_base_url=payload.api_base_url, encrypted_api_key=AISecretService.encrypt(payload.api_key),
        key_hint=AISecretService.hint(payload.api_key), organization_id=payload.organization_id,
        project_id=payload.project_id, default_model=payload.default_model, enabled=payload.enabled,
        priority=payload.priority, timeout_seconds=payload.timeout_seconds, max_retries=payload.max_retries,
        capabilities=payload.capabilities, settings=payload.settings, created_by=current_user.id,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return provider_response(row)


@router.patch("/providers/{provider_id}", response_model=AIProviderResponse)
async def update_provider(guild_id: int, provider_id: UUID, payload: AIProviderUpdate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    row = await AIGatewayService(session).get_provider(guild_id, provider_id)
    values = payload.model_dump(exclude_unset=True)
    api_key = values.pop("api_key", None)
    if api_key is not None:
        row.encrypted_api_key = AISecretService.encrypt(api_key)
        row.key_hint = AISecretService.hint(api_key)
    for key, value in values.items():
        setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return provider_response(row)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(guild_id: int, provider_id: UUID, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    row = await AIGatewayService(session).get_provider(guild_id, provider_id)
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)


@router.post("/providers/{provider_id}/test", response_model=AIProviderTestResponse)
async def test_provider(guild_id: int, provider_id: UUID, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    service = AIGatewayService(session)
    row = await service.get_provider(guild_id, provider_id)
    try:
        health, latency, detail = await service.test_provider(row)
    except Exception as exc:
        health, latency, detail = "error", 0, str(exc)[:500]
    row.last_health_status = health
    row.last_health_latency_ms = latency
    row.last_health_check_at = datetime.now(timezone.utc)
    row.last_error = None if health == "connected" else detail
    if health == "connected":
        row.consecutive_failures = 0
        row.circuit_open_until = None
    await session.commit()
    return AIProviderTestResponse(provider_id=row.id, status=health, latency_ms=latency, detail=detail)


@router.get("/routes", response_model=list[AIRouteResponse])
async def list_routes(guild_id: int, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    result = await session.execute(select(GuildAIRoute).where(GuildAIRoute.guild_id == guild_id).order_by(GuildAIRoute.capability))
    return [await route_response(session, row) for row in result.scalars().all()]


@router.put("/routes/{capability}", response_model=AIRouteResponse)
async def upsert_route(guild_id: int, capability: str, payload: AIRouteUpsert, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    capability = capability.strip().lower()
    result = await session.execute(select(GuildAIRoute).where(GuildAIRoute.guild_id == guild_id, GuildAIRoute.capability == capability))
    row = result.scalar_one_or_none()
    if row is None:
        row = GuildAIRoute(guild_id=guild_id, capability=capability)
        session.add(row)
        await session.flush()
    row.enabled = payload.enabled
    row.max_total_attempts = payload.max_total_attempts
    row.failure_threshold = payload.failure_threshold
    row.cooldown_seconds = payload.cooldown_seconds
    row.configuration = payload.configuration

    provider_ids = {target.provider_id for target in payload.targets}
    if provider_ids:
        providers = await session.execute(select(GuildAIProvider.id).where(GuildAIProvider.guild_id == guild_id, GuildAIProvider.id.in_(provider_ids)))
        found = set(providers.scalars().all())
        missing = provider_ids - found
        if missing:
            raise HTTPException(status_code=400, detail=f"Providers do not belong to this server: {', '.join(map(str, missing))}")

    await session.execute(delete(GuildAIRouteTarget).where(GuildAIRouteTarget.route_id == row.id))
    for target in sorted(payload.targets, key=lambda x: x.position):
        session.add(GuildAIRouteTarget(
            route_id=row.id, provider_id=target.provider_id, position=target.position,
            model=target.model, timeout_seconds=target.timeout_seconds,
            retries=target.retries, enabled=target.enabled, configuration=target.configuration,
        ))
    await session.commit()
    await session.refresh(row)
    return await route_response(session, row)
