from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.plugin_worker.api_registry import PluginAPIRegistry
from app.plugin_worker.dynamic_loader import (
    PluginDynamicLoader,
    PluginDynamicLoaderError,
)
from app.plugin_worker.event_bus import RuntimeEventBus
from app.plugin_worker.runtime_manager import (
    PluginRuntimeAdapter,
    PluginRuntimeManager,
    PluginRuntimeSnapshot,
    PluginRuntimeStateName,
)
from app.plugin_worker.runtime_registry import PluginRuntimeRegistry
from app.plugins.manifest import PluginManifest


class PluginHotReloadError(RuntimeError):
    """Raised when a runtime swap fails, including rollback failures."""


@dataclass(frozen=True)
class PluginHotReloadReport:
    plugin_key: str
    previous_version: str
    new_version: str
    committed: bool
    rolled_back: bool
    final_snapshot: PluginRuntimeSnapshot
    error: str | None = None


@dataclass
class _ActiveRuntime:
    loader: PluginDynamicLoader
    adapter: PluginRuntimeAdapter
    manifest: PluginManifest
    plugin_root: Path


class PluginHotReloadCoordinator:
    """
    Atomic in-process backend plugin replacement.

    Candidate code is imported and validated before the active runtime is
    stopped. The candidate is committed only after start and health checks.
    On failure, the previous adapter is registered and started again.
    """

    def __init__(
        self,
        *,
        manager: PluginRuntimeManager,
        registry: PluginRuntimeRegistry,
        event_bus: RuntimeEventBus,
        api_registry: PluginAPIRegistry | None = None,
        hook_timeout_seconds: float = 20.0,
        operation_timeout_seconds: float = 60.0,
    ) -> None:
        if operation_timeout_seconds <= 0:
            raise ValueError(
                "Operation timeout must be greater than zero"
            )

        self.manager = manager
        self.registry = registry
        self.event_bus = event_bus
        self.api_registry = api_registry or PluginAPIRegistry()
        self.hook_timeout_seconds = hook_timeout_seconds
        self.operation_timeout_seconds = operation_timeout_seconds
        self._active: dict[str, _ActiveRuntime] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def attach_active(
        self,
        *,
        plugin_key: str,
        loader: PluginDynamicLoader,
        adapter: PluginRuntimeAdapter,
    ) -> None:
        registered = self.registry.get(plugin_key)
        key = registered.manifest.plugin_key
        self._active[key] = _ActiveRuntime(
            loader=loader,
            adapter=adapter,
            manifest=registered.manifest,
            plugin_root=registered.plugin_root,
        )
        self._locks.setdefault(key, asyncio.Lock())

    async def reload(
        self,
        *,
        plugin_key: str,
        candidate_manifest: PluginManifest,
        candidate_root: Path,
        configuration: dict[str, Any] | None = None,
        services: dict[str, Any] | None = None,
        require_healthy: bool = True,
    ) -> PluginHotReloadReport:
        key = plugin_key.strip().lower()
        if candidate_manifest.plugin_key != key:
            raise PluginHotReloadError(
                "Candidate manifest plugin key does not match "
                f"requested plugin: {candidate_manifest.plugin_key} != {key}"
            )

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            try:
                return await asyncio.wait_for(
                    self._reload_locked(
                        key=key,
                        candidate_manifest=candidate_manifest,
                        candidate_root=candidate_root,
                        configuration=configuration,
                        services=services,
                        require_healthy=require_healthy,
                    ),
                    timeout=self.operation_timeout_seconds,
                )
            except TimeoutError as exc:
                raise PluginHotReloadError(
                    f"Hot reload timed out after "
                    f"{self.operation_timeout_seconds:g} seconds"
                ) from exc

    async def _reload_locked(
        self,
        *,
        key: str,
        candidate_manifest: PluginManifest,
        candidate_root: Path,
        configuration: dict[str, Any] | None,
        services: dict[str, Any] | None,
        require_healthy: bool,
    ) -> PluginHotReloadReport:
        current = self.manager.get(key)
        active = self._active.get(key)
        if active is None:
            raise PluginHotReloadError(
                f"Active loader is not attached: {key}"
            )

        was_running = current.state == PluginRuntimeStateName.RUNNING
        if current.state in {
            PluginRuntimeStateName.STARTING,
            PluginRuntimeStateName.STOPPING,
        }:
            raise PluginHotReloadError(
                f"Plugin runtime is busy: {key} ({current.state})"
            )

        candidate_registry = PluginRuntimeRegistry()
        candidate_registry.register(
            manifest=candidate_manifest,
            plugin_root=candidate_root,
        )
        candidate_loader = PluginDynamicLoader(
            event_bus=self.event_bus,
            registry=candidate_registry,
            api_registry=self.api_registry,
            hook_timeout_seconds=self.hook_timeout_seconds,
        )

        try:
            candidate_adapter = candidate_loader.load(
                key,
                configuration=configuration,
                services=services,
            )
        except Exception as exc:
            raise PluginHotReloadError(
                f"Candidate staging failed: {exc}"
            ) from exc

        await self.event_bus.publish(
            "plugin.reload.staged",
            source=key,
            payload={
                "plugin_key": key,
                "from_version": current.version,
                "to_version": candidate_manifest.version,
            },
        )

        old_adapter = active.adapter
        old_version = current.version
        old_manifest = active.manifest
        old_root = active.plugin_root
        old_loader = active.loader

        try:
            if current.state in {
                PluginRuntimeStateName.RUNNING,
                PluginRuntimeStateName.FAILED,
            }:
                await self.manager.stop(key)

            await self.manager.unregister(key)
            await self.manager.register(
                plugin_key=key,
                version=candidate_manifest.version,
                adapter=candidate_adapter,
            )
            started = await self.manager.start(key)

            if require_healthy:
                checked = await self.manager.check_health(key)
                if not checked.healthy:
                    raise PluginHotReloadError(
                        "Candidate health check failed: "
                        f"{checked.health or checked.last_error}"
                    )
                started = checked

        except Exception as candidate_error:
            rollback_error: Exception | None = None

            try:
                try:
                    candidate_state = self.manager.get(key)
                except Exception:
                    candidate_state = None

                if (
                    candidate_state is not None
                    and candidate_state.state
                    in {
                        PluginRuntimeStateName.RUNNING,
                        PluginRuntimeStateName.FAILED,
                    }
                ):
                    try:
                        await self.manager.stop(key)
                    except Exception:
                        pass

                try:
                    await self.manager.unregister(key)
                except Exception:
                    pass

                candidate_loader.unload_module(key)

                await self.manager.register(
                    plugin_key=key,
                    version=old_version,
                    adapter=old_adapter,
                )
                if was_running:
                    restored = await self.manager.start(key)
                    restored = await self.manager.check_health(key)
                else:
                    restored = self.manager.get(key)

                self.registry.register(
                    manifest=old_manifest,
                    plugin_root=old_root,
                    replace=True,
                )
                self._active[key] = active

            except Exception as exc:
                rollback_error = exc
                try:
                    restored = self.manager.get(key)
                except Exception:
                    restored = current

            await self.event_bus.publish(
                "plugin.reload.rolled_back",
                source=key,
                payload={
                    "plugin_key": key,
                    "from_version": old_version,
                    "candidate_version": candidate_manifest.version,
                    "error": str(candidate_error),
                    "rollback_error": (
                        str(rollback_error)
                        if rollback_error is not None
                        else None
                    ),
                },
            )

            if rollback_error is not None:
                raise PluginHotReloadError(
                    f"Candidate failed: {candidate_error}; "
                    f"rollback also failed: {rollback_error}"
                ) from candidate_error

            return PluginHotReloadReport(
                plugin_key=key,
                previous_version=old_version,
                new_version=candidate_manifest.version,
                committed=False,
                rolled_back=True,
                final_snapshot=restored,
                error=str(candidate_error),
            )

        self.registry.register(
            manifest=candidate_manifest,
            plugin_root=candidate_root,
            replace=True,
        )
        self._active[key] = _ActiveRuntime(
            loader=candidate_loader,
            adapter=candidate_adapter,
            manifest=candidate_manifest,
            plugin_root=candidate_root.resolve(),
        )

        old_loader.unload_module(key)

        await self.event_bus.publish(
            "plugin.reload.committed",
            source=key,
            payload={
                "plugin_key": key,
                "from_version": old_version,
                "to_version": candidate_manifest.version,
            },
        )

        return PluginHotReloadReport(
            plugin_key=key,
            previous_version=old_version,
            new_version=candidate_manifest.version,
            committed=True,
            rolled_back=False,
            final_snapshot=started,
            error=None,
        )
