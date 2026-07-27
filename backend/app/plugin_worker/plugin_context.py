from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.plugin_worker.event_bus import RuntimeEventBus
from app.plugin_worker.runtime_registry import PluginRuntimeRegistry
from app.plugins.manifest import PluginManifest


@dataclass
class PluginContext:
    plugin_key: str
    version: str
    plugin_root: Path
    manifest: PluginManifest
    event_bus: RuntimeEventBus
    registry: PluginRuntimeRegistry
    logger: logging.Logger
    configuration: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)

    def get_service(self, name: str) -> Any:
        key = name.strip()
        if not key:
            raise KeyError("Service name must not be empty")
        if key not in self.services:
            raise KeyError(
                f"Service is unavailable for {self.plugin_key}: {key}"
            )
        return self.services[key]

    def export_service(self, name: str, value: Any) -> None:
        key = name.strip()
        if not key:
            raise ValueError("Service name must not be empty")
        if key in self.services:
            raise ValueError(
                f"Service is already exported by "
                f"{self.plugin_key}: {key}"
            )
        self.services[key] = value
