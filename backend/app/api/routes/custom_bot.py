from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.billing import BillingSubscription
from app.models.core import User
from app.services.plugin_control_service import PluginControlService

router = APIRouter(tags=["Custom Discord Bot"])
PLAN_KEY = "__custom_bot__"
VAULT_KEY = "custom_discord_bot"


class CustomBotInput(BaseModel):
    token: str = Field(min_length=20, max_length=256)


async def active_subscription(session: AsyncSession, guild_id: int) -> BillingSubscription | None:
    now = datetime.now(UTC)
    return await session.scalar(select(BillingSubscription).where(
        BillingSubscription.guild_id == guild_id,
        BillingSubscription.plugin_key == PLAN_KEY,
        BillingSubscription.status == "active",
        BillingSubscription.expires_at > now,
    ))


@router.get("/discord/guilds/{guild_id}/custom-bot")
async def get_custom_bot(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, user, guild_id)
    vault = PluginControlService(session)
    configured = bool(await vault.get_secret(VAULT_KEY, "token", "guild", str(guild_id)))
    username = await vault.get_secret(VAULT_KEY, "username", "guild", str(guild_id))
    application_id = await vault.get_secret(VAULT_KEY, "application_id", "guild", str(guild_id))
    subscription = await active_subscription(session, guild_id)
    invite_url = None
    if application_id and subscription:
        permissions = 8
        invite_url = f"https://discord.com/oauth2/authorize?client_id={application_id}&permissions={permissions}&scope=bot%20applications.commands&guild_id={guild_id}&disable_guild_select=true"
    return {
        "configured": configured,
        "username": username,
        "application_id": application_id,
        "invite_url": invite_url,
        "subscription_active": subscription is not None,
        "service_active": subscription is not None and configured,
        "expires_at": subscription.expires_at if subscription else None,
    }


@router.put("/discord/guilds/{guild_id}/custom-bot")
async def save_custom_bot(payload: CustomBotInput, guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, user, guild_id)
    if await active_subscription(session, guild_id) is None:
        raise HTTPException(402, "An active Custom Discord Bot subscription is required")
    token = payload.token.strip()
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get("https://discord.com/api/v10/users/@me", headers={"Authorization": f"Bot {token}"})
    if response.status_code != 200:
        raise HTTPException(400, "Discord rejected this bot token")
    identity = response.json()
    if not identity.get("bot"):
        raise HTTPException(400, "Only a Discord bot token can be used")
    application_id = str(identity.get("id"))
    username = str(identity.get("global_name") or identity.get("username") or "Discord bot")
    vault = PluginControlService(session)
    for name, value in (("token", token), ("application_id", application_id), ("username", username)):
        await vault.put_secret(VAULT_KEY, name, value, "guild", str(guild_id), user.id)
    return {"configured": True, "username": username, "application_id": application_id,
            "invite_url": f"https://discord.com/oauth2/authorize?client_id={application_id}&permissions=8&scope=bot%20applications.commands&guild_id={guild_id}&disable_guild_select=true"}


@router.delete("/discord/guilds/{guild_id}/custom-bot")
async def delete_custom_bot(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, user, guild_id)
    vault = PluginControlService(session)
    for name in ("token", "application_id", "username"):
        try:
            await vault.delete_secret(VAULT_KEY, name, "guild", str(guild_id), user.id)
        except LookupError:
            pass
    return {"configured": False}
