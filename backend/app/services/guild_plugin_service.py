from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugins import (
    GuildPluginInstallation,
    PluginMarketplaceItem,
    PluginRegistry,
)
from app.schemas.guild_plugins import (
    GuildPluginInstallationResponse,
    GuildPluginMarketplaceItemResponse,
)
from app.services.plugin_runtime_instance_service import (
    PluginRuntimeConflictError,
    PluginRuntimeInstanceService,
)


class GuildPluginConflictError(Exception):
    pass


class GuildPluginService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def marketplace(self, guild_id: int):
        marketplace_plugins = list(
            (
                await self.session.execute(
                    select(PluginMarketplaceItem)
                    .where(
                        PluginMarketplaceItem.status == "published",
                        PluginMarketplaceItem.published.is_(True),
                    )
                    .order_by(
                        PluginMarketplaceItem.verified.desc(),
                        PluginMarketplaceItem.name.asc(),
                    )
                )
            ).scalars().all()
        )
        discovered_plugins = list(
            (
                await self.session.execute(
                    select(PluginRegistry)
                    .where(PluginRegistry.healthy.is_(True))
                    .order_by(PluginRegistry.name.asc())
                )
            ).scalars().all()
        )
        installs = list(
            (
                await self.session.execute(
                    select(GuildPluginInstallation).where(
                        GuildPluginInstallation.guild_id == guild_id
                    )
                )
            ).scalars().all()
        )

        by_key = {
            installation.plugin_key: installation
            for installation in installs
        }
        available: dict[str, GuildPluginMarketplaceItemResponse] = {}

        for plugin in marketplace_plugins:
            installation = by_key.get(plugin.plugin_key)
            available[plugin.plugin_key] = GuildPluginMarketplaceItemResponse(
                plugin_key=plugin.plugin_key,
                name=plugin.name,
                version=plugin.version,
                summary=plugin.summary,
                category=plugin.category,
                icon_url=plugin.icon_url,
                verified=plugin.verified,
                installed=installation is not None,
                enabled=bool(installation and installation.enabled),
                installation_status=(
                    installation.status if installation else None
                ),
            )

        for plugin in discovered_plugins:
            installation = by_key.get(plugin.plugin_key)
            existing = available.get(plugin.plugin_key)
            available[plugin.plugin_key] = GuildPluginMarketplaceItemResponse(
                plugin_key=plugin.plugin_key,
                name=plugin.name,
                version=plugin.version,
                summary=plugin.description,
                category=(
                    str((plugin.manifest or {}).get("category") or "local")
                ),
                icon_url=(
                    str((plugin.manifest or {}).get("icon_url"))
                    if (plugin.manifest or {}).get("icon_url")
                    else None
                ),
                verified=existing.verified if existing else False,
                installed=installation is not None,
                enabled=bool(installation and installation.enabled),
                installation_status=(
                    installation.status if installation else None
                ),
            )

        return sorted(
            available.values(),
            key=lambda item: (item.installed, item.name.lower()),
        )

    async def list_installed(self, guild_id: int):
        rows = list(
            (
                await self.session.execute(
                    select(GuildPluginInstallation)
                    .where(
                        GuildPluginInstallation.guild_id == guild_id
                    )
                    .order_by(
                        GuildPluginInstallation.created_at.asc()
                    )
                )
            ).scalars().all()
        )

        return [self._response(row) for row in rows]

    async def install(
        self,
        guild_id: int,
        plugin_key: str,
        user_id: UUID | None,
    ):
        marketplace_plugin = (
            await self.session.execute(
                select(PluginMarketplaceItem).where(
                    PluginMarketplaceItem.plugin_key == plugin_key,
                    PluginMarketplaceItem.status == "published",
                    PluginMarketplaceItem.published.is_(True),
                )
            )
        ).scalar_one_or_none()
        discovered_plugin = (
            await self.session.execute(
                select(PluginRegistry).where(
                    PluginRegistry.plugin_key == plugin_key,
                    PluginRegistry.healthy.is_(True),
                )
            )
        ).scalar_one_or_none()

        if marketplace_plugin is None and discovered_plugin is None:
            raise LookupError(
                "available plugin not found"
            )

        if await self._find(guild_id, plugin_key):
            raise GuildPluginConflictError(
                "plugin is already installed for this server"
            )

        now = datetime.now(timezone.utc)

        row = GuildPluginInstallation(
            id=uuid4(),
            guild_id=guild_id,
            plugin_key=plugin_key,
            status="installed",
            enabled=False,
            configuration={},
            installed_by_user_id=user_id,
            installed_at=now,
            created_at=now,
            updated_at=now,
        )

        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)

        return self._response(row)

    async def set_enabled(
        self,
        guild_id: int,
        plugin_key: str,
        enabled: bool,
    ):
        row = await self._required(guild_id, plugin_key)
        now = datetime.now(timezone.utc)

        if enabled and plugin_key == "first_introduction":
            config = row.configuration or {}
            if "groups" in config:
                groups = [group for group in config["groups"] if group.get("enabled")]
                if not groups or any(not group.get("language_roles") or not group.get("channel_id")
                                     or not group.get("access_role_id") for group in groups):
                    raise ValueError("Configure a channel, access role and language roles for each enabled language group")
            elif not config.get("language_roles") or not config.get("channel_id"):
                raise ValueError("Configure language roles and a thread before enabling")
        if enabled and plugin_key == "translator_groups":
            groups = (row.configuration or {}).get("groups", [])
            if not any(group.get("enabled") and len({item.get("language") for item in group.get("channels", [])}) >= 2 for group in groups):
                raise ValueError("Configure an enabled translation group with channels in at least two languages")

        previous_enabled = row.enabled
        previous_status = row.status
        previous_enabled_at = row.enabled_at
        previous_disabled_at = row.disabled_at
        previous_error = row.last_error
        previous_updated_at = row.updated_at

        row.enabled = enabled
        row.status = "enabled" if enabled else "disabled"
        row.enabled_at = now if enabled else row.enabled_at
        row.disabled_at = None if enabled else now
        row.last_error = None
        row.updated_at = now

        await self.session.flush()

        runtime = PluginRuntimeInstanceService(self.session)

        try:
            if enabled:
                try:
                    # start() commits both runtime and guild installation
                    # changes because both services use the same session.
                    await runtime.start(guild_id, plugin_key)
                except PluginRuntimeConflictError:
                    # Idempotent enable: a running runtime is already the
                    # desired state.
                    await self.session.commit()
            else:
                try:
                    # stop() also commits the guild installation changes.
                    await runtime.stop(guild_id, plugin_key)
                except LookupError:
                    # A plugin may be installed but never started.
                    await self.session.commit()

        except Exception as exc:
            await self.session.rollback()

            # Restore the in-memory values for callers that retain the
            # current service/session after the exception.
            row.enabled = previous_enabled
            row.status = previous_status
            row.enabled_at = previous_enabled_at
            row.disabled_at = previous_disabled_at
            row.last_error = previous_error
            row.updated_at = previous_updated_at

            raise exc

        await self.session.refresh(row)
        return self._response(row)

    async def update_configuration(
        self,
        guild_id: int,
        plugin_key: str,
        configuration: dict,
    ):
        if plugin_key == "first_introduction":
            raise ValueError("Use the Language Selection settings page")
        if plugin_key == "translator_groups":
            raise ValueError("Use the Translator Groups settings page")
        row = await self._required(guild_id, plugin_key)

        row.configuration = configuration
        row.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(row)

        return self._response(row)

    async def uninstall(
        self,
        guild_id: int,
        plugin_key: str,
    ):
        row = await self._required(guild_id, plugin_key)

        runtime = PluginRuntimeInstanceService(self.session)

        try:
            await runtime.stop(guild_id, plugin_key)
        except LookupError:
            # No runtime instance was ever created.
            pass

        await self.session.delete(row)
        await self.session.commit()

    async def _find(
        self,
        guild_id: int,
        plugin_key: str,
    ):
        return (
            await self.session.execute(
                select(GuildPluginInstallation).where(
                    GuildPluginInstallation.guild_id == guild_id,
                    GuildPluginInstallation.plugin_key == plugin_key,
                )
            )
        ).scalar_one_or_none()

    async def _required(
        self,
        guild_id: int,
        plugin_key: str,
    ):
        row = await self._find(guild_id, plugin_key)

        if row is None:
            raise LookupError(
                "plugin is not installed for this server"
            )

        return row

    @staticmethod
    def _response(
        installation: GuildPluginInstallation,
    ) -> GuildPluginInstallationResponse:
        return GuildPluginInstallationResponse(
            id=installation.id,
            guild_id=installation.guild_id,
            plugin_key=installation.plugin_key,
            status=installation.status,
            enabled=installation.enabled,
            configuration=installation.configuration or {},
            installed_by_user_id=(
                installation.installed_by_user_id
            ),
            installed_at=installation.installed_at,
            enabled_at=installation.enabled_at,
            disabled_at=installation.disabled_at,
            last_health_check_at=(
                installation.last_health_check_at
            ),
            last_error=installation.last_error,
            created_at=installation.created_at,
            updated_at=installation.updated_at,
        )
