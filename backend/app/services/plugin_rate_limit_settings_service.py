from __future__ import annotations

from typing import Any

from sqlalchemy import select, text

from app.db.session import AsyncSessionFactory
from app.models.plugins import (
    GuildPluginInstallation,
    PluginRuntimeInstance,
)
from app.services.plugin_rate_limit_service import (
    plugin_rate_limiter,
)


SUPPORTED_SCOPES = frozenset({
    "runtime.context",
    "runtime.token.refresh",
    "runtime.read",
    "discord.send.message",
})


class PluginRateLimitSettingsError(ValueError):
    pass


class PluginRateLimitSettingsService:
    @staticmethod
    def normalize_limits(
        raw_limits: dict[str, Any],
    ) -> dict[str, int]:
        normalized: dict[str, int] = {}

        for scope, value in raw_limits.items():
            if scope not in SUPPORTED_SCOPES:
                raise PluginRateLimitSettingsError(
                    f"Unsupported Plugin API scope: {scope}"
                )

            if isinstance(value, bool) or not isinstance(
                value,
                int,
            ):
                raise PluginRateLimitSettingsError(
                    f"Rate limit for '{scope}' must be an integer"
                )

            if value < 0:
                raise PluginRateLimitSettingsError(
                    f"Rate limit for '{scope}' cannot be negative"
                )

            if (
                value
                > plugin_rate_limiter.maximum_custom_limit
            ):
                raise PluginRateLimitSettingsError(
                    f"Rate limit for '{scope}' exceeds "
                    f"maximum value "
                    f"{plugin_rate_limiter.maximum_custom_limit}"
                )

            normalized[scope] = value

        return normalized

    @staticmethod
    def _manifest_limits(
        runtime: PluginRuntimeInstance | None,
    ) -> dict[str, int]:
        if runtime is None:
            return {}

        manifest = runtime.manifest_json or {}

        if not isinstance(manifest, dict):
            return {}

        raw_limits = manifest.get("rate_limits", {})

        if not isinstance(raw_limits, dict):
            return {}

        result: dict[str, int] = {}

        for scope, value in raw_limits.items():
            if scope not in SUPPORTED_SCOPES:
                continue

            if isinstance(value, bool):
                continue

            if not isinstance(value, int):
                continue

            if value < 0:
                continue

            result[scope] = min(
                value,
                plugin_rate_limiter.maximum_custom_limit,
            )

        return result

    @classmethod
    async def get_settings(
        cls,
        *,
        guild_id: int,
        plugin_key: str,
    ) -> dict[str, Any]:
        async with AsyncSessionFactory() as session:
            installation = (
                await session.execute(
                    select(
                        GuildPluginInstallation
                    ).where(
                        GuildPluginInstallation.guild_id
                        == guild_id,
                        GuildPluginInstallation.plugin_key
                        == plugin_key,
                    )
                )
            ).scalar_one_or_none()

            runtime = (
                await session.execute(
                    select(
                        PluginRuntimeInstance
                    ).where(
                        PluginRuntimeInstance.guild_id
                        == guild_id,
                        PluginRuntimeInstance.plugin_key
                        == plugin_key,
                    )
                )
            ).scalar_one_or_none()

        if installation is None:
            raise PluginRateLimitSettingsError(
                "Plugin installation was not found"
            )

        installation_limits = cls.normalize_limits(
            installation.rate_limits_json or {}
        )

        manifest_limits = cls._manifest_limits(runtime)

        effective_limits = []

        for scope in sorted(SUPPORTED_SCOPES):
            limit, source = (
                await plugin_rate_limiter.resolve_limit(
                    guild_id=guild_id,
                    plugin_key=plugin_key,
                    scope=scope,
                )
            )

            effective_limits.append({
                "scope": scope,
                "limit": limit,
                "source": source,
            })

        return {
            "guild_id": guild_id,
            "plugin_key": plugin_key,
            "installation_limits": installation_limits,
            "manifest_limits": manifest_limits,
            "effective_limits": effective_limits,
        }

    @classmethod
    async def update_settings(
        cls,
        *,
        guild_id: int,
        plugin_key: str,
        limits: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = cls.normalize_limits(limits)

        async with AsyncSessionFactory() as session:
            installation = (
                await session.execute(
                    select(
                        GuildPluginInstallation
                    ).where(
                        GuildPluginInstallation.guild_id
                        == guild_id,
                        GuildPluginInstallation.plugin_key
                        == plugin_key,
                    )
                )
            ).scalar_one_or_none()

            if installation is None:
                raise PluginRateLimitSettingsError(
                    "Plugin installation was not found"
                )

            installation.rate_limits_json = normalized

            await session.execute(
                text("""
                    DELETE FROM plugins.rate_limit_windows
                    WHERE guild_id = :guild_id
                      AND plugin_key = :plugin_key
                """),
                {
                    "guild_id": guild_id,
                    "plugin_key": plugin_key,
                },
            )

            await session.commit()

        return await cls.get_settings(
            guild_id=guild_id,
            plugin_key=plugin_key,
        )
