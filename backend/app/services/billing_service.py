from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingPluginPlan, BillingSubscription
from app.models.plugins import GuildPluginInstallation


FREE_PLUGIN_KEYS = frozenset({
    "welcome", "audit_security", "backup_restore", "guild_dm_broadcast",
    "antiflood", "ai_automod",
})

def normalize_plugin_key(value: str) -> str:
    return value.strip().lower().replace("-", "_")

class BillingRequiredError(Exception):
    pass

class BillingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_entitled(self, guild_id: int, plugin_key: str) -> bool:
        key = normalize_plugin_key(plugin_key)
        if key in FREE_PLUGIN_KEYS:
            return True
        now = datetime.now(timezone.utc)
        subscription = (await self.session.execute(
            select(BillingSubscription).where(
                BillingSubscription.guild_id == guild_id,
                BillingSubscription.plugin_key == key,
                BillingSubscription.status == "active",
                BillingSubscription.starts_at <= now,
                BillingSubscription.expires_at > now,
            )
        )).scalar_one_or_none()
        return subscription is not None

    async def require_entitlement(self, guild_id: int, plugin_key: str) -> None:
        if not await self.is_entitled(guild_id, plugin_key):
            raise BillingRequiredError("An active subscription is required to enable this plugin")

    async def list_plans(self):
        return list((await self.session.execute(select(BillingPluginPlan).order_by(BillingPluginPlan.plugin_key))).scalars())

    async def list_subscriptions(self, guild_id: int | None = None):
        query = select(BillingSubscription).order_by(BillingSubscription.expires_at.desc())
        if guild_id is not None:
            query = query.where(BillingSubscription.guild_id == guild_id)
        return list((await self.session.execute(query)).scalars())

    async def expired_enabled_plugins(self) -> list[tuple[int, str]]:
        installations = list((await self.session.execute(select(GuildPluginInstallation).where(
            GuildPluginInstallation.enabled.is_(True)
        ))).scalars())
        result = []
        for item in installations:
            if normalize_plugin_key(item.plugin_key) not in FREE_PLUGIN_KEYS and not await self.is_entitled(item.guild_id, item.plugin_key):
                result.append((item.guild_id, item.plugin_key))
        return result
