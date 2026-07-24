from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import (
    require_guild_management,
)
from app.db.session import get_db_session
from app.models.core import User
from app.schemas.plugin_rate_limits import (
    PluginRateLimitSettingsResponse,
    PluginRateLimitUpdate,
)
from app.services.plugin_rate_limit_settings_service import (
    PluginRateLimitSettingsError,
    PluginRateLimitSettingsService,
)


router = APIRouter(
    prefix=(
        "/discord/guilds/{guild_id}/plugins/"
        "{plugin_key}/rate-limits"
    ),
    tags=["Plugin Rate Limits"],
)


@router.get(
    "",
    response_model=PluginRateLimitSettingsResponse,
)
async def get_plugin_rate_limits(
    guild_id: int,
    plugin_key: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PluginRateLimitSettingsResponse:
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    try:
        data = (
            await PluginRateLimitSettingsService
            .get_settings(
                guild_id=guild_id,
                plugin_key=plugin_key,
            )
        )
    except PluginRateLimitSettingsError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PluginRateLimitSettingsResponse(
        **data
    )


@router.put(
    "",
    response_model=PluginRateLimitSettingsResponse,
)
async def update_plugin_rate_limits(
    guild_id: int,
    plugin_key: str,
    payload: PluginRateLimitUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PluginRateLimitSettingsResponse:
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    try:
        data = (
            await PluginRateLimitSettingsService
            .update_settings(
                guild_id=guild_id,
                plugin_key=plugin_key,
                limits=payload.limits,
            )
        )
    except PluginRateLimitSettingsError as exc:
        detail = str(exc)

        response_status = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.lower()
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )

        raise HTTPException(
            status_code=response_status,
            detail=detail,
        ) from exc

    return PluginRateLimitSettingsResponse(
        **data
    )
