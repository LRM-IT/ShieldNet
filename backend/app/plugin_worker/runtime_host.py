from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.plugin_worker.api_registry import PluginAPIRegistry
from app.plugin_worker.dynamic_loader import DynamicPluginAdapter, PluginDynamicLoader
from app.plugin_worker.event_bus import RuntimeEventBus
from app.plugin_worker.runtime_manager import (
    PluginRuntimeManager,
    PluginRuntimeSnapshot,
    PluginRuntimeStateName,
)
from app.plugin_worker.runtime_registry import PluginRuntimeRegistry
from app.plugins.manifest import PluginManifest


class PluginRuntimeHostError(RuntimeError):
    """Raised when a plugin cannot be activated in the worker runtime."""


@dataclass(frozen=True)
class PluginRuntimeActivation:
    plugin_key: str
    version: str
    snapshot: PluginRuntimeSnapshot


class PluginRuntimeHost:
    """Persistent in-process runtime host owned by the plugin worker."""

    def __init__(self) -> None:
        self.event_bus = RuntimeEventBus()
        self.registry = PluginRuntimeRegistry()
        self.api_registry = PluginAPIRegistry()
        self.manager = PluginRuntimeManager()
        self.loader = PluginDynamicLoader(
            event_bus=self.event_bus,
            registry=self.registry,
            api_registry=self.api_registry,
        )
        self._adapters: dict[str, DynamicPluginAdapter] = {}

    async def activate(
        self,
        *,
        manifest: PluginManifest,
        plugin_root: Path,
        configuration: dict[str, Any] | None = None,
        services: dict[str, Any] | None = None,
    ) -> PluginRuntimeActivation:
        key = manifest.plugin_key
        root = plugin_root.resolve()

        if key in self._adapters:
            raise PluginRuntimeHostError(
                f"Plugin runtime is already active: {key}; "
                "use the update pipeline for replacement"
            )

        registry_registered = False
        manager_registered = False

        try:
            self.registry.register(manifest=manifest, plugin_root=root)
            registry_registered = True

            adapter = self.loader.load(
                key,
                configuration=configuration,
                services=services,
            )

            await self.manager.register(
                plugin_key=key,
                version=manifest.version,
                adapter=adapter,
            )
            manager_registered = True

            await self.manager.start(key)
            snapshot = await self.manager.check_health(key)
            if snapshot.state != PluginRuntimeStateName.RUNNING or not snapshot.healthy:
                raise PluginRuntimeHostError(
                    "Plugin runtime health check failed: "
                    f"{snapshot.health or snapshot.last_error}"
                )

            self._adapters[key] = adapter
            return PluginRuntimeActivation(
                plugin_key=key,
                version=manifest.version,
                snapshot=snapshot,
            )
        except Exception as exc:
            if manager_registered:
                try:
                    current = self.manager.get(key)
                    if current.state in {
                        PluginRuntimeStateName.RUNNING,
                        PluginRuntimeStateName.FAILED,
                    }:
                        try:
                            await self.manager.stop(key)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    await self.manager.unregister(key)
                except Exception:
                    pass

            self.loader.unload_module(key)

            if registry_registered:
                try:
                    self.registry.unregister(key)
                except Exception:
                    pass

            if isinstance(exc, PluginRuntimeHostError):
                raise
            raise PluginRuntimeHostError(
                f"Plugin runtime activation failed: {exc}"
            ) from exc

    async def deactivate(self, plugin_key: str) -> None:
        key = plugin_key.strip().lower()
        if key not in self._adapters:
            self.loader.unload_module(key)
            return

        try:
            current = self.manager.get(key)
            if current.state in {
                PluginRuntimeStateName.RUNNING,
                PluginRuntimeStateName.FAILED,
            }:
                await self.manager.stop(key)
        finally:
            try:
                await self.manager.unregister(key)
            except Exception:
                pass
            self.loader.unload_module(key)
            try:
                self.registry.unregister(key)
            except Exception:
                pass
            self._adapters.pop(key, None)


runtime_host = PluginRuntimeHost()
