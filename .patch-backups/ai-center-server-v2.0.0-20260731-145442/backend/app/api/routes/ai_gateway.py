from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.ai_gateway import GuildAIModuleSetting, GuildAIProvider
from app.models.core import User
from app.schemas.ai_gateway import AIProviderCreate, AIProviderResponse, AIProviderTestResponse, AIProviderUpdate, AIModuleSettingResponse, AIModuleSettingUpsert
from app.services.ai_gateway import AIGatewayService
from app.services.ai_secrets import AISecretService

router = APIRouter(prefix="/discord/guilds/{guild_id}/ai", tags=["Server AI Gateway"])


def provider_response(row: GuildAIProvider) -> AIProviderResponse:
    return AIProviderResponse(
        id=row.id, guild_id=str(row.guild_id), name=row.name, provider_type=row.provider_type,
        api_base_url=row.api_base_url, key_hint=row.key_hint, organization_id=row.organization_id,
        project_id=row.project_id, default_model=row.default_model, enabled=row.enabled,
        priority=row.priority, timeout_seconds=row.timeout_seconds, max_retries=row.max_retries,
        capabilities=row.capabilities or [], settings=row.settings or {}, last_health_status=row.last_health_status,
        last_health_latency_ms=row.last_health_latency_ms, last_health_check_at=row.last_health_check_at,
        last_error=row.last_error, created_at=row.created_at, updated_at=row.updated_at,
    )


@router.get("/providers", response_model=list[AIProviderResponse])
async def list_providers(guild_id: int, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    result = await session.execute(select(GuildAIProvider).where(GuildAIProvider.guild_id == guild_id).order_by(GuildAIProvider.priority, GuildAIProvider.name))
    return [provider_response(item) for item in result.scalars().all()]


@router.post("/providers", response_model=AIProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(guild_id: int, payload: AIProviderCreate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    row = GuildAIProvider(guild_id=guild_id, name=payload.name, provider_type=payload.provider_type,
        api_base_url=payload.api_base_url, encrypted_api_key=AISecretService.encrypt(payload.api_key), key_hint=AISecretService.hint(payload.api_key),
        organization_id=payload.organization_id, project_id=payload.project_id, default_model=payload.default_model,
        enabled=payload.enabled, priority=payload.priority, timeout_seconds=payload.timeout_seconds, max_retries=payload.max_retries,
        capabilities=payload.capabilities, settings=payload.settings, created_by=current_user.id)
    session.add(row)
    await session.commit(); await session.refresh(row)
    return provider_response(row)


@router.patch("/providers/{provider_id}", response_model=AIProviderResponse)
async def update_provider(guild_id: int, provider_id: UUID, payload: AIProviderUpdate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    row = await AIGatewayService(session).get_provider(guild_id, provider_id)
    values = payload.model_dump(exclude_unset=True)
    api_key = values.pop("api_key", None)
    if api_key is not None:
        row.encrypted_api_key = AISecretService.encrypt(api_key); row.key_hint = AISecretService.hint(api_key)
    for key, value in values.items(): setattr(row, key, value)
    await session.commit(); await session.refresh(row)
    return provider_response(row)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(guild_id: int, provider_id: UUID, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    row = await AIGatewayService(session).get_provider(guild_id, provider_id)
    await session.delete(row); await session.commit(); return Response(status_code=204)


@router.post("/providers/{provider_id}/test", response_model=AIProviderTestResponse)
async def test_provider(guild_id: int, provider_id: UUID, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    service=AIGatewayService(session); row=await service.get_provider(guild_id, provider_id)
    try: health, latency, detail = await service.test_provider(row)
    except Exception as exc: health, latency, detail = "error", 0, str(exc)[:500]
    row.last_health_status=health; row.last_health_latency_ms=latency; row.last_health_check_at=datetime.now(timezone.utc); row.last_error=None if health=="connected" else detail
    await session.commit()
    return AIProviderTestResponse(provider_id=row.id, status=health, latency_ms=latency, detail=detail)


@router.get("/modules", response_model=list[AIModuleSettingResponse])
async def list_module_settings(guild_id: int, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    result=await session.execute(select(GuildAIModuleSetting).where(GuildAIModuleSetting.guild_id==guild_id).order_by(GuildAIModuleSetting.module_key, GuildAIModuleSetting.capability))
    return [AIModuleSettingResponse(id=x.id,guild_id=str(x.guild_id),module_key=x.module_key,capability=x.capability,provider_id=x.provider_id,model=x.model,fallback_provider_ids=x.fallback_provider_ids or [],enabled=x.enabled,configuration=x.configuration or {},created_at=x.created_at,updated_at=x.updated_at) for x in result.scalars().all()]


@router.put("/modules/{module_key}/{capability}", response_model=AIModuleSettingResponse)
async def upsert_module_setting(guild_id:int,module_key:str,capability:str,payload:AIModuleSettingUpsert,current_user:User=Depends(get_current_user),session:AsyncSession=Depends(get_db_session)):
    await require_guild_management(session,current_user,guild_id)
    if payload.provider_id is not None: await AIGatewayService(session).get_provider(guild_id,payload.provider_id)
    result=await session.execute(select(GuildAIModuleSetting).where(GuildAIModuleSetting.guild_id==guild_id,GuildAIModuleSetting.module_key==module_key,GuildAIModuleSetting.capability==capability))
    row=result.scalar_one_or_none()
    if row is None:
        row=GuildAIModuleSetting(guild_id=guild_id,module_key=module_key,capability=capability); session.add(row)
    row.provider_id=payload.provider_id; row.model=payload.model; row.fallback_provider_ids=[str(x) for x in payload.fallback_provider_ids]; row.enabled=payload.enabled; row.configuration=payload.configuration
    await session.commit(); await session.refresh(row)
    return AIModuleSettingResponse(id=row.id,guild_id=str(row.guild_id),module_key=row.module_key,capability=row.capability,provider_id=row.provider_id,model=row.model,fallback_provider_ids=row.fallback_provider_ids or [],enabled=row.enabled,configuration=row.configuration or {},created_at=row.created_at,updated_at=row.updated_at)
