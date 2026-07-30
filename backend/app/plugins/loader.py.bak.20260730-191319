from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from app.plugins.base import BackendPlugin, PluginContext
from app.plugins.manifest import PluginManifest, PluginManifestError


class PluginLoadError(RuntimeError):
    pass


@dataclass
class LoadedBackendPlugin:
    manifest: PluginManifest
    instance: BackendPlugin
    module: ModuleType


class BackendPluginLoader:
    def __init__(self, *, services: dict[str, Any] | None = None) -> None:
        self.services = services or {}
        self.loaded: dict[str, LoadedBackendPlugin] = {}

    async def load(self, plugin_root: Path, manifest: PluginManifest) -> LoadedBackendPlugin:
        key = manifest.plugin_key
        if key in self.loaded:
            return self.loaded[key]
        entrypoint = manifest.entrypoints.backend
        if not manifest.components.backend or not entrypoint:
            raise PluginLoadError(f"Plugin {key} has no backend component")

        module_name, separator, object_name = entrypoint.partition(":")
        if not separator or not module_name or not object_name:
            raise PluginManifestError(
                f"Plugin {key}: backend entrypoint must use 'module.path:ClassName'"
            )

        root = str(plugin_root.resolve())
        added_path = root not in sys.path
        if added_path:
            sys.path.insert(0, root)
        try:
            module = importlib.import_module(module_name)
            plugin_type = getattr(module, object_name, None)
            if plugin_type is None or not inspect.isclass(plugin_type):
                raise PluginLoadError(f"Plugin {key}: entrypoint class {object_name!r} was not found")
            if not issubclass(plugin_type, BackendPlugin):
                raise PluginLoadError(f"Plugin {key}: entrypoint must inherit BackendPlugin")
            context = PluginContext(manifest=manifest, plugin_root=plugin_root, services=dict(self.services))
            instance = plugin_type(context)
            await instance.startup()
            loaded = LoadedBackendPlugin(manifest=manifest, instance=instance, module=module)
            self.loaded[key] = loaded
            return loaded
        except Exception as exc:
            if isinstance(exc, (PluginLoadError, PluginManifestError)):
                raise
            raise PluginLoadError(f"Plugin {key}: load failed: {exc}") from exc
        finally:
            if added_path:
                try:
                    sys.path.remove(root)
                except ValueError:
                    pass

    async def unload(self, plugin_key: str) -> bool:
        loaded = self.loaded.pop(plugin_key, None)
        if loaded is None:
            return False
        await loaded.instance.shutdown()
        return True
