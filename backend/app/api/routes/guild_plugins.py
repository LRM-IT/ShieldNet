from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.schemas.guild_plugins import GuildPluginInstallationResponse, GuildPluginMarketplaceItemResponse, GuildPluginSettingsUpdate
from app.services.guild_plugin_service import GuildPluginConflictError, GuildPluginService
from app.services.billing_service import BillingRequiredError

router = APIRouter(tags=["Guild Plugin Marketplace"])

async def authorize(guild_id: int, user: User, session: AsyncSession):
    await require_guild_management(session, user, guild_id)

@router.get("/discord/guilds/{guild_id}/marketplace", response_model=list[GuildPluginMarketplaceItemResponse])
async def marketplace(guild_id: int, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await authorize(guild_id, current_user, session)
    return await GuildPluginService(session).marketplace(guild_id)

@router.get("/discord/guilds/{guild_id}/plugins", response_model=list[GuildPluginInstallationResponse])
async def installed(guild_id: int, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await authorize(guild_id, current_user, session)
    return await GuildPluginService(session).list_installed(guild_id)

@router.post("/discord/guilds/{guild_id}/plugins/{plugin_key}/install", response_model=GuildPluginInstallationResponse, status_code=201)
async def install(guild_id: int, plugin_key: str, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await authorize(guild_id, current_user, session)
    try:
        return await GuildPluginService(session).install(guild_id, plugin_key, current_user.id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except GuildPluginConflictError as exc:
        raise HTTPException(409, str(exc)) from exc

@router.post("/discord/guilds/{guild_id}/plugins/{plugin_key}/enable", response_model=GuildPluginInstallationResponse)
async def enable(guild_id: int, plugin_key: str, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await authorize(guild_id, current_user, session)
    try:
        return await GuildPluginService(session).set_enabled(guild_id, plugin_key, True)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except BillingRequiredError as exc:
        raise HTTPException(402, str(exc)) from exc

@router.post("/discord/guilds/{guild_id}/plugins/{plugin_key}/disable", response_model=GuildPluginInstallationResponse)
async def disable(guild_id: int, plugin_key: str, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await authorize(guild_id, current_user, session)
    try:
        return await GuildPluginService(session).set_enabled(guild_id, plugin_key, False)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc

@router.patch("/discord/guilds/{guild_id}/plugins/{plugin_key}/settings", response_model=GuildPluginInstallationResponse)
async def settings(guild_id: int, plugin_key: str, payload: GuildPluginSettingsUpdate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await authorize(guild_id, current_user, session)
    try:
        return await GuildPluginService(session).update_configuration(guild_id, plugin_key, payload.configuration)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

@router.delete("/discord/guilds/{guild_id}/plugins/{plugin_key}", status_code=204)
async def uninstall(guild_id: int, plugin_key: str, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await authorize(guild_id, current_user, session)
    try:
        await GuildPluginService(session).uninstall(guild_id, plugin_key)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
