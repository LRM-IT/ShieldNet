from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.plugin_worker.dependency_resolver import (
    DependencyResolution,
    PluginDependencyResolver,
)
from app.plugins.manifest import PluginManifest


class PluginRuntimeRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegisteredPlugin:
    manifest: PluginManifest
    plugin_root: Path


class PluginRuntimeRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, RegisteredPlugin] = {}
        self._resolver = PluginDependencyResolver()

    def register(
        self,
        *,
        manifest: PluginManifest,
        plugin_root: Path,
        replace: bool = False,
    ) -> RegisteredPlugin:
        root = plugin_root.resolve()
        if not root.is_dir():
            raise PluginRuntimeRegistryError(
                f"Plugin root does not exist: {root}"
            )

        existing = self._plugins.get(manifest.plugin_key)
        if existing is not None and not replace:
            raise PluginRuntimeRegistryError(
                f"Plugin already registered: "
                f"{manifest.plugin_key}"
            )

        registered = RegisteredPlugin(
            manifest=manifest,
            plugin_root=root,
        )
        self._plugins[manifest.plugin_key] = registered
        return registered

    def unregister(self, plugin_key: str) -> None:
        key = plugin_key.strip().lower()
        if key not in self._plugins:
            raise PluginRuntimeRegistryError(
                f"Plugin is not registered: {key}"
            )
        del self._plugins[key]

    def get(self, plugin_key: str) -> RegisteredPlugin:
        key = plugin_key.strip().lower()
        plugin = self._plugins.get(key)
        if plugin is None:
            raise PluginRuntimeRegistryError(
                f"Plugin is not registered: {key}"
            )
        return plugin

    def list(self) -> tuple[RegisteredPlugin, ...]:
        return tuple(
            self._plugins[key]
            for key in sorted(self._plugins)
        )

    def resolve_all(self) -> DependencyResolution:
        return self._resolver.resolve(
            item.manifest
            for item in self._plugins.values()
        )

    def resolve_selected(
        self,
        plugin_keys: tuple[str, ...],
    ) -> DependencyResolution:
        manifests = {
            key: item.manifest
            for key, item in self._plugins.items()
        }
        return self._resolver.resolve_selected(
            manifests,
            plugin_keys,
        )
