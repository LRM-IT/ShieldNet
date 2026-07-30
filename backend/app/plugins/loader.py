from __future__ import annotations

import hashlib
import importlib
import importlib.util
import inspect
import re
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
    """
    Load every plugin backend in its own Python module namespace.

    Plugins commonly use the same entrypoint name, for example:

        runtime:WelcomePlugin
        runtime:VotingPlugin
        runtime:AntiFloodPlugin

    Using importlib.import_module("runtime") directly causes Python to reuse
    sys.modules["runtime"] from the first plugin. This loader resolves the
    module inside the individual plugin directory and assigns a unique module
    name, preventing cross-plugin module-cache collisions.
    """

    def __init__(self, *, services: dict[str, Any] | None = None) -> None:
        self.services = services or {}
        self.loaded: dict[str, LoadedBackendPlugin] = {}

    @staticmethod
    def _safe_key(value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_")
        return normalized or "plugin"

    @classmethod
    def _unique_module_name(
        cls,
        plugin_key: str,
        plugin_root: Path,
        module_name: str,
    ) -> str:
        digest = hashlib.sha256(
            str(plugin_root.resolve()).encode("utf-8")
        ).hexdigest()[:12]

        safe_plugin = cls._safe_key(plugin_key)
        safe_module = cls._safe_key(module_name.replace(".", "_"))

        return (
            f"_shieldnet_plugin_{safe_plugin}_{digest}_{safe_module}"
        )

    @staticmethod
    def _resolve_module_path(
        plugin_root: Path,
        module_name: str,
    ) -> tuple[Path, bool]:
        """
        Resolve a manifest module name relative to the plugin package.

        Supported forms:
          runtime
          runtime.py
          backend.plugin
          backend/plugin.py
          package
        """
        cleaned = module_name.strip()

        if cleaned.endswith(".py"):
            relative = Path(cleaned)
        else:
            relative = Path(*cleaned.split("."))

        candidates: list[tuple[Path, bool]] = []

        if relative.suffix == ".py":
            candidates.append((plugin_root / relative, False))
        else:
            candidates.append(
                (plugin_root / relative.with_suffix(".py"), False)
            )
            candidates.append(
                (plugin_root / relative / "__init__.py", True)
            )

        root_resolved = plugin_root.resolve()

        for candidate, is_package in candidates:
            resolved = candidate.resolve()

            if (
                resolved != root_resolved
                and root_resolved not in resolved.parents
            ):
                continue

            if resolved.is_file():
                return resolved, is_package

        expected = ", ".join(str(item[0]) for item in candidates)

        raise PluginLoadError(
            "Plugin backend module was not found. "
            f"Checked: {expected}"
        )

    @classmethod
    def _load_local_module(
        cls,
        *,
        plugin_key: str,
        plugin_root: Path,
        module_name: str,
    ) -> ModuleType:
        module_path, is_package = cls._resolve_module_path(
            plugin_root,
            module_name,
        )

        unique_name = cls._unique_module_name(
            plugin_key,
            plugin_root,
            module_name,
        )

        # Always discard a stale module created by an earlier scan/reload.
        sys.modules.pop(unique_name, None)

        if is_package:
            spec = importlib.util.spec_from_file_location(
                unique_name,
                module_path,
                submodule_search_locations=[
                    str(module_path.parent.resolve())
                ],
            )
        else:
            spec = importlib.util.spec_from_file_location(
                unique_name,
                module_path,
            )

        if spec is None or spec.loader is None:
            raise PluginLoadError(
                f"Unable to create import specification for {module_path}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = module

        root = str(plugin_root.resolve())
        added_path = root not in sys.path

        if added_path:
            sys.path.insert(0, root)

        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(unique_name, None)
            raise
        finally:
            if added_path:
                try:
                    sys.path.remove(root)
                except ValueError:
                    pass

        return module

    async def load(
        self,
        plugin_root: Path,
        manifest: PluginManifest,
    ) -> LoadedBackendPlugin:
        key = manifest.plugin_key

        if key in self.loaded:
            return self.loaded[key]

        entrypoint = manifest.entrypoints.backend

        if not manifest.components.backend or not entrypoint:
            raise PluginLoadError(
                f"Plugin {key} has no backend component"
            )

        module_name, separator, object_name = entrypoint.partition(":")

        if not separator or not module_name or not object_name:
            raise PluginManifestError(
                f"Plugin {key}: backend entrypoint must use "
                "'module.path:ClassName'"
            )

        try:
            module = self._load_local_module(
                plugin_key=key,
                plugin_root=plugin_root,
                module_name=module_name,
            )

            plugin_type = getattr(module, object_name, None)

            if plugin_type is None or not inspect.isclass(plugin_type):
                available_classes = sorted(
                    name
                    for name, value in vars(module).items()
                    if inspect.isclass(value)
                )

                suffix = (
                    f"; available classes: {', '.join(available_classes)}"
                    if available_classes
                    else "; module contains no classes"
                )

                raise PluginLoadError(
                    f"Plugin {key}: entrypoint class "
                    f"{object_name!r} was not found{suffix}"
                )

            if not issubclass(plugin_type, BackendPlugin):
                raise PluginLoadError(
                    f"Plugin {key}: entrypoint must inherit BackendPlugin"
                )

            context = PluginContext(
                manifest=manifest,
                plugin_root=plugin_root,
                services=dict(self.services),
            )

            instance = plugin_type(context)
            await instance.startup()

            loaded = LoadedBackendPlugin(
                manifest=manifest,
                instance=instance,
                module=module,
            )

            self.loaded[key] = loaded
            return loaded

        except Exception as exc:
            if isinstance(
                exc,
                (PluginLoadError, PluginManifestError),
            ):
                raise

            raise PluginLoadError(
                f"Plugin {key}: load failed: {exc}"
            ) from exc

    async def unload(self, plugin_key: str) -> bool:
        loaded = self.loaded.pop(plugin_key, None)

        if loaded is None:
            return False

        await loaded.instance.shutdown()
        sys.modules.pop(loaded.module.__name__, None)

        return True
