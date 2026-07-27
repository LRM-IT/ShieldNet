from __future__ import annotations

import asyncio
import importlib.util
import inspect
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from app.plugin_worker.api_registry import PluginAPIRegistry
from app.plugin_worker.event_bus import RuntimeEventBus
from app.plugin_worker.plugin_context import PluginContext
from app.plugin_worker.runtime_registry import (
    PluginRuntimeRegistry,
    RegisteredPlugin,
)


class PluginDynamicLoaderError(RuntimeError):
    """Raised when plugin backend code cannot be loaded safely."""


@dataclass(frozen=True)
class LoadedPluginModule:
    plugin_key: str
    version: str
    module_name: str
    module: ModuleType
    instance: Any
    context: PluginContext
    entrypoint_path: Path


class DynamicPluginAdapter:
    def __init__(
        self,
        loaded: LoadedPluginModule,
        *,
        api_registry: PluginAPIRegistry,
        hook_timeout_seconds: float,
    ) -> None:
        self.loaded = loaded
        self.api_registry = api_registry
        self.hook_timeout_seconds = hook_timeout_seconds
        self._loaded_hook_completed = False
        self._started = False

    async def start(self) -> None:
        if self._started:
            return

        if not self._loaded_hook_completed:
            await self._invoke_hook("on_load")
            self._loaded_hook_completed = True

        try:
            await self._invoke_hook("on_start")
        except Exception:
            await self._safe_invoke("on_unload")
            self._loaded_hook_completed = False
            raise

        self._started = True
        await self.loaded.context.event_bus.publish(
            "plugin.started",
            source=self.loaded.plugin_key,
            payload={
                "plugin_key": self.loaded.plugin_key,
                "version": self.loaded.version,
            },
        )

    async def stop(self) -> None:
        errors: list[str] = []

        if self._started:
            try:
                await self._invoke_hook("on_stop")
            except Exception as exc:
                errors.append(f"on_stop: {exc}")
            self._started = False

        if self._loaded_hook_completed:
            try:
                await self._invoke_hook("on_unload")
            except Exception as exc:
                errors.append(f"on_unload: {exc}")
            self._loaded_hook_completed = False

        self.api_registry.remove_plugin(self.loaded.plugin_key)

        await self.loaded.context.event_bus.publish(
            "plugin.stopped",
            source=self.loaded.plugin_key,
            payload={
                "plugin_key": self.loaded.plugin_key,
                "version": self.loaded.version,
                "errors": errors,
            },
        )

        if errors:
            raise PluginDynamicLoaderError("; ".join(errors))

    async def health(self) -> dict[str, Any]:
        hook = self._find_hook("health")
        if hook is None:
            return {
                "status": "ready" if self._started else "stopped",
                "plugin_key": self.loaded.plugin_key,
                "version": self.loaded.version,
            }

        result = await self._execute(hook)
        if result is None:
            result = {"status": "ready"}
        if not isinstance(result, dict):
            raise PluginDynamicLoaderError(
                "Plugin health hook must return a dictionary"
            )
        return dict(result)

    async def _safe_invoke(self, hook_name: str) -> None:
        try:
            await self._invoke_hook(hook_name)
        except Exception:
            return

    async def _invoke_hook(self, hook_name: str) -> Any:
        hook = self._find_hook(hook_name)
        if hook is None:
            return None
        return await self._execute(hook)

    def _find_hook(self, hook_name: str) -> Any:
        instance_hook = getattr(
            self.loaded.instance,
            hook_name,
            None,
        )
        if callable(instance_hook):
            return instance_hook

        module_hook = getattr(
            self.loaded.module,
            hook_name,
            None,
        )
        if callable(module_hook):
            return module_hook
        return None

    async def _execute(self, hook: Any) -> Any:
        try:
            signature = inspect.signature(hook)
            positional = [
                parameter
                for parameter in signature.parameters.values()
                if parameter.kind in {
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                }
                and parameter.default
                is inspect.Parameter.empty
            ]
        except (TypeError, ValueError):
            positional = []

        result = (
            hook(self.loaded.context)
            if positional
            else hook()
        )

        if inspect.isawaitable(result):
            try:
                return await asyncio.wait_for(
                    result,
                    timeout=self.hook_timeout_seconds,
                )
            except TimeoutError as exc:
                raise PluginDynamicLoaderError(
                    f"Plugin lifecycle hook timed out after "
                    f"{self.hook_timeout_seconds:g} seconds"
                ) from exc

        return result


class PluginDynamicLoader:
    def __init__(
        self,
        *,
        event_bus: RuntimeEventBus,
        registry: PluginRuntimeRegistry,
        api_registry: PluginAPIRegistry | None = None,
        hook_timeout_seconds: float = 20.0,
    ) -> None:
        if hook_timeout_seconds <= 0:
            raise ValueError(
                "Hook timeout must be greater than zero"
            )

        self.event_bus = event_bus
        self.registry = registry
        self.api_registry = api_registry or PluginAPIRegistry()
        self.hook_timeout_seconds = hook_timeout_seconds
        self._loaded: dict[str, LoadedPluginModule] = {}

    def load(
        self,
        plugin_key: str,
        *,
        configuration: dict[str, Any] | None = None,
        services: dict[str, Any] | None = None,
        replace: bool = False,
    ) -> DynamicPluginAdapter:
        registered = self.registry.get(plugin_key)
        key = registered.manifest.plugin_key

        if key in self._loaded and not replace:
            raise PluginDynamicLoaderError(
                f"Plugin module is already loaded: {key}"
            )

        if key in self._loaded:
            self.unload_module(key)

        loaded = self._load_registered(
            registered,
            configuration=configuration,
            services=services,
        )
        self._loaded[key] = loaded

        return DynamicPluginAdapter(
            loaded,
            api_registry=self.api_registry,
            hook_timeout_seconds=self.hook_timeout_seconds,
        )

    def get_loaded(self, plugin_key: str) -> LoadedPluginModule:
        key = plugin_key.strip().lower()
        loaded = self._loaded.get(key)
        if loaded is None:
            raise PluginDynamicLoaderError(
                f"Plugin module is not loaded: {key}"
            )
        return loaded

    def list_loaded(self) -> tuple[LoadedPluginModule, ...]:
        return tuple(
            self._loaded[key]
            for key in sorted(self._loaded)
        )

    def unload_module(self, plugin_key: str) -> None:
        key = plugin_key.strip().lower()
        loaded = self._loaded.pop(key, None)
        if loaded is None:
            return
        self.api_registry.remove_plugin(key)
        sys.modules.pop(loaded.module_name, None)

    def _load_registered(
        self,
        registered: RegisteredPlugin,
        *,
        configuration: dict[str, Any] | None,
        services: dict[str, Any] | None,
    ) -> LoadedPluginModule:
        manifest = registered.manifest
        entrypoint = manifest.entrypoints.backend
        if not manifest.components.backend or not entrypoint:
            raise PluginDynamicLoaderError(
                f"Plugin has no backend entrypoint: "
                f"{manifest.plugin_key}"
            )

        path_part, separator, attribute = entrypoint.partition(":")
        entrypoint_path = self._resolve_entrypoint(
            registered.plugin_root,
            path_part,
        )

        module_name = (
            f"shieldnet_plugin_{manifest.plugin_key.replace('-', '_')}_"
            f"{manifest.version.replace('.', '_').replace('-', '_')}"
        )

        spec = importlib.util.spec_from_file_location(
            module_name,
            entrypoint_path,
        )
        if spec is None or spec.loader is None:
            raise PluginDynamicLoaderError(
                f"Cannot create import specification: "
                f"{entrypoint_path}"
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(module_name, None)
            raise PluginDynamicLoaderError(
                f"Plugin import failed for "
                f"{manifest.plugin_key}: {exc}"
            ) from exc

        logger = logging.getLogger(
            f"shieldnet.plugin.{manifest.plugin_key}"
        )
        context = PluginContext(
            plugin_key=manifest.plugin_key,
            version=manifest.version,
            plugin_root=registered.plugin_root,
            manifest=manifest,
            event_bus=self.event_bus,
            registry=self.registry,
            logger=logger,
            configuration=dict(configuration or {}),
            services=dict(services or {}),
        )

        instance = self._create_instance(
            module,
            attribute if separator else None,
            context,
        )

        return LoadedPluginModule(
            plugin_key=manifest.plugin_key,
            version=manifest.version,
            module_name=module_name,
            module=module,
            instance=instance,
            context=context,
            entrypoint_path=entrypoint_path,
        )

    @staticmethod
    def _create_instance(
        module: ModuleType,
        attribute: str | None,
        context: PluginContext,
    ) -> Any:
        if attribute:
            target = getattr(module, attribute, None)
            if target is None:
                raise PluginDynamicLoaderError(
                    f"Entrypoint attribute not found: {attribute}"
                )
            if inspect.isclass(target):
                return PluginDynamicLoader._call_factory(
                    target,
                    context,
                )
            if callable(target):
                return PluginDynamicLoader._call_factory(
                    target,
                    context,
                )
            return target

        factory = getattr(module, "create_plugin", None)
        if callable(factory):
            return PluginDynamicLoader._call_factory(
                factory,
                context,
            )

        instance = getattr(module, "plugin", None)
        return instance if instance is not None else module

    @staticmethod
    def _call_factory(factory: Any, context: PluginContext) -> Any:
        try:
            signature = inspect.signature(factory)
            required = [
                parameter
                for parameter in signature.parameters.values()
                if parameter.kind in {
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                }
                and parameter.default is inspect.Parameter.empty
            ]
        except (TypeError, ValueError):
            required = []

        result = factory(context) if required else factory()
        if inspect.isawaitable(result):
            raise PluginDynamicLoaderError(
                "Async plugin factories are not supported; "
                "use async lifecycle hooks instead"
            )
        return result

    @staticmethod
    def _resolve_entrypoint(
        plugin_root: Path,
        entrypoint: str,
    ) -> Path:
        raw = entrypoint.strip()
        if not raw:
            raise PluginDynamicLoaderError(
                "Backend entrypoint must not be empty"
            )

        if raw.endswith(".py") or "/" in raw or "\\" in raw:
            relative = Path(raw)
        else:
            relative = Path(*raw.split(".")).with_suffix(".py")

        if relative.is_absolute():
            raise PluginDynamicLoaderError(
                "Absolute plugin entrypoints are forbidden"
            )

        root = plugin_root.resolve()
        candidate = (root / relative).resolve()

        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PluginDynamicLoaderError(
                "Plugin entrypoint escapes plugin root"
            ) from exc

        if not candidate.is_file():
            raise PluginDynamicLoaderError(
                f"Plugin entrypoint does not exist: {candidate}"
            )
        return candidate
