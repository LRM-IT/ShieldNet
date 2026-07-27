from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PluginAPIRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class PluginAPIExport:
    plugin_key: str
    name: str
    value: Any


class PluginAPIRegistry:
    def __init__(self) -> None:
        self._exports: dict[tuple[str, str], PluginAPIExport] = {}

    def publish(
        self,
        *,
        plugin_key: str,
        name: str,
        value: Any,
        replace: bool = False,
    ) -> PluginAPIExport:
        plugin = self._normalize(plugin_key, "plugin_key")
        api_name = self._normalize(name, "name")
        key = (plugin, api_name)

        if key in self._exports and not replace:
            raise PluginAPIRegistryError(
                f"Plugin API already published: {plugin}.{api_name}"
            )

        export = PluginAPIExport(
            plugin_key=plugin,
            name=api_name,
            value=value,
        )
        self._exports[key] = export
        return export

    def get(self, plugin_key: str, name: str) -> Any:
        plugin = self._normalize(plugin_key, "plugin_key")
        api_name = self._normalize(name, "name")
        export = self._exports.get((plugin, api_name))
        if export is None:
            raise PluginAPIRegistryError(
                f"Plugin API not found: {plugin}.{api_name}"
            )
        return export.value

    def remove(self, plugin_key: str, name: str) -> None:
        plugin = self._normalize(plugin_key, "plugin_key")
        api_name = self._normalize(name, "name")
        self._exports.pop((plugin, api_name), None)

    def remove_plugin(self, plugin_key: str) -> int:
        plugin = self._normalize(plugin_key, "plugin_key")
        keys = [
            key for key in self._exports
            if key[0] == plugin
        ]
        for key in keys:
            del self._exports[key]
        return len(keys)

    def list(self) -> tuple[PluginAPIExport, ...]:
        return tuple(
            self._exports[key]
            for key in sorted(self._exports)
        )

    @staticmethod
    def _normalize(value: str, field: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise PluginAPIRegistryError(
                f"{field} must not be empty"
            )
        return normalized
