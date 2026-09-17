from __future__ import annotations

import functools
import inspect
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar


class Capability(StrEnum):
    DISCORD_READ_GUILD = "discord.read.guild"
    DISCORD_READ_MEMBERS = "discord.read.members"
    DISCORD_READ_MESSAGES = "discord.read.messages"
    DISCORD_SEND_MESSAGE = "discord.send.message"
    DISCORD_MANAGE_MEMBERS = "discord.manage.members"
    DISCORD_MANAGE_MESSAGES = "discord.manage.messages"
    DISCORD_MANAGE_ROLES = "discord.manage.roles"
    DISCORD_MANAGE_CHANNELS = "discord.manage.channels"
    DISCORD_MANAGE_WEBHOOKS = "discord.manage.webhooks"

    STORAGE_READ = "storage.read"
    STORAGE_WRITE = "storage.write"
    STORAGE_DELETE = "storage.delete"

    RUNTIME_READ = "runtime.read"
    RUNTIME_CONTROL = "runtime.control"

    SCHEDULER_READ = "scheduler.read"
    SCHEDULER_JOBS = "scheduler.jobs"

    NETWORK_OUTBOUND = "network.outbound"
    NETWORK_LOCAL = "network.local"

    AI_CHAT = "ai.chat"
    AI_EMBEDDING = "ai.embedding"
    AI_MODERATION = "ai.moderation"

    AUDIT_WRITE = "audit.write"
    ACTIVITY_TRACK = "activity.track"
    SECURITY_AUDIT = "security.audit"
    BACKUPS_MANAGE = "backups.manage"
    CONFIGURATION_RESTORE = "configuration.restore"
    NETWORK_MANAGE = "network.manage"
    EVENTS_MANAGE = "events.manage"
    WARS_MANAGE = "wars.manage"

    EVENTS_SUBSCRIBE = "events.subscribe"
    EVENTS_PUBLISH = "events.publish"


ALL_CAPABILITIES = frozenset(item.value for item in Capability)


class CapabilityDenied(PermissionError):
    def __init__(
        self,
        capability: str,
        *,
        plugin_key: str,
        guild_id: int,
    ) -> None:
        self.capability = capability
        self.plugin_key = plugin_key
        self.guild_id = guild_id

        super().__init__(
            f"Plugin '{plugin_key}' has no capability "
            f"'{capability}' for guild {guild_id}"
        )


@dataclass(frozen=True, slots=True)
class PluginContext:
    guild_id: int
    plugin_key: str
    package_path: Path
    generation: int
    permissions: frozenset[str]
    runtime_token: str
    backend_url: str
    _backend_client: Any = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    def has(
        self,
        capability: Capability | str,
    ) -> bool:
        value = (
            capability.value
            if isinstance(capability, Capability)
            else str(capability)
        )

        return value in self.permissions

    def require(
        self,
        capability: Capability | str,
    ) -> None:
        value = (
            capability.value
            if isinstance(capability, Capability)
            else str(capability)
        )

        if value not in ALL_CAPABILITIES:
            raise ValueError(
                f"Unknown ShieldNet capability: {value}"
            )

        if value not in self.permissions:
            raise CapabilityDenied(
                value,
                plugin_key=self.plugin_key,
                guild_id=self.guild_id,
            )

    def require_all(
        self,
        *capabilities: Capability | str,
    ) -> None:
        for capability in capabilities:
            self.require(capability)

    def require_any(
        self,
        *capabilities: Capability | str,
    ) -> None:
        if not capabilities:
            raise ValueError(
                "require_any() needs at least one capability"
            )

        if any(self.has(capability) for capability in capabilities):
            return

        values = [
            capability.value
            if isinstance(capability, Capability)
            else str(capability)
            for capability in capabilities
        ]

        raise CapabilityDenied(
            " | ".join(values),
            plugin_key=self.plugin_key,
            guild_id=self.guild_id,
        )

    @property
    def backend(self):
        """
        Return one cached SDK client for the plugin process.
        The client keeps the rotated Runtime Token in memory.
        """
        from app.plugin_sdk.backend_client import (
            PluginBackendClient,
        )

        client = self._backend_client

        if client is None:
            client = PluginBackendClient(context=self)
            object.__setattr__(
                self,
                "_backend_client",
                client,
            )

        return client

    def public_info(self) -> dict[str, Any]:
        return {
            "guild_id": self.guild_id,
            "plugin_key": self.plugin_key,
            "package_path": str(self.package_path),
            "generation": self.generation,
            "permissions": sorted(self.permissions),
            "backend_url": self.backend_url,
            "runtime_token_present": bool(self.runtime_token),
        }


P = ParamSpec("P")
R = TypeVar("R")


def requires(
    *capabilities: Capability | str,
) -> Callable[
    [Callable[P, R] | Callable[P, Awaitable[R]]],
    Callable[P, R] | Callable[P, Awaitable[R]],
]:
    if not capabilities:
        raise ValueError(
            "requires() needs at least one capability"
        )

    def decorator(
        function: Callable[P, R] | Callable[P, Awaitable[R]],
    ) -> Callable[P, R] | Callable[P, Awaitable[R]]:
        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def async_wrapper(
                context: PluginContext,
                *args: P.args,
                **kwargs: P.kwargs,
            ) -> R:
                context.require_all(*capabilities)

                return await function(
                    context,
                    *args,
                    **kwargs,
                )

            return async_wrapper

        @functools.wraps(function)
        def sync_wrapper(
            context: PluginContext,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            context.require_all(*capabilities)

            return function(
                context,
                *args,
                **kwargs,
            )

        return sync_wrapper

    return decorator
