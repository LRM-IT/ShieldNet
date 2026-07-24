from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import (
    require_guild_management,
)
from app.db.session import get_db_session
from app.models.core import User
from app.schemas.plugin_usage import (
    PluginUsageHistoryResponse,
    PluginUsageSummaryResponse,
)
from app.services.plugin_usage_service import (
    PluginUsageError,
    PluginUsageService,
)


router = APIRouter(
    prefix=(
        "/discord/guilds/{guild_id}/plugins/"
        "{plugin_key}/usage"
    ),
    tags=["Plugin Runtime Usage"],
)


@router.get(
    "",
    response_model=PluginUsageSummaryResponse,
)
async def get_plugin_usage(
    guild_id: int,
    plugin_key: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PluginUsageSummaryResponse:
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    try:
        data = await PluginUsageService.get_summary(
            guild_id=guild_id,
            plugin_key=plugin_key,
        )
    except PluginUsageError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return PluginUsageSummaryResponse(**data)


@router.get(
    "/history",
    response_model=PluginUsageHistoryResponse,
)
async def get_plugin_usage_history(
    guild_id: int,
    plugin_key: str,
    days: int = Query(
        default=7,
        description="Supported periods: 7, 30, 90",
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PluginUsageHistoryResponse:
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    try:
        data = await PluginUsageService.get_history(
            guild_id=guild_id,
            plugin_key=plugin_key,
            days=days,
        )
    except PluginUsageError as exc:
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

    return PluginUsageHistoryResponse(**data)
