from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.plugin_worker.runtime_host import (
    PluginRuntimeActivation,
    PluginRuntimeHost,
    PluginRuntimeHostError,
)
from app.plugins.manifest import PluginManifest


class PluginRuntimeTransactionError(RuntimeError):
    """Raised when a runtime transaction cannot be completed safely."""


@dataclass(frozen=True)
class RuntimeLeakReport:
    plugin_key: str
    module_names: tuple[str, ...]
    adapter_present: bool
    registry_present: bool
    manager_present: bool

    @property
    def clean(self) -> bool:
        return not (
            self.module_names
            or self.adapter_present
            or self.registry_present
            or self.manager_present
        )


class PluginRuntimeTransaction:
    """Prepare, commit, or roll back one plugin runtime activation."""

    def __init__(
        self,
        host: PluginRuntimeHost,
        *,
        manifest: PluginManifest,
        plugin_root: Path,
        configuration: dict[str, Any] | None = None,
        services: dict[str, Any] | None = None,
    ) -> None:
        self.host = host
        self.manifest = manifest
        self.plugin_root = plugin_root.resolve()
        self.configuration = dict(configuration or {})
        self.services = dict(services or {})
        self.activation: PluginRuntimeActivation | None = None
        self.prepared = False
        self.committed = False
        self.rolled_back = False

    async def prepare(self) -> PluginRuntimeActivation:
        if self.prepared:
            raise PluginRuntimeTransactionError(
                "Runtime transaction has already been prepared"
            )
        if self.committed or self.rolled_back:
            raise PluginRuntimeTransactionError(
                "Runtime transaction is already closed"
            )

        try:
            self.activation = await self.host.activate(
                manifest=self.manifest,
                plugin_root=self.plugin_root,
                configuration=self.configuration,
                services=self.services,
            )
            self.prepared = True
            return self.activation
        except Exception:
            await self._cleanup_failed_prepare()
            raise

    async def commit(self) -> PluginRuntimeActivation:
        if not self.prepared or self.activation is None:
            raise PluginRuntimeTransactionError(
                "Runtime transaction must be prepared before commit"
            )
        if self.rolled_back:
            raise PluginRuntimeTransactionError(
                "Rolled-back runtime transaction cannot be committed"
            )

        key = self.manifest.plugin_key
        current = self.host._adapters.get(key)
        if current is None:
            raise PluginRuntimeTransactionError(
                f"Prepared runtime disappeared before commit: {key}"
            )

        snapshot = await self.host.manager.check_health(key)
        if not snapshot.healthy:
            raise PluginRuntimeTransactionError(
                f"Runtime became unhealthy before commit: {snapshot.health}"
            )

        self.committed = True
        return PluginRuntimeActivation(
            plugin_key=key,
            version=self.manifest.version,
            snapshot=snapshot,
        )

    async def rollback(self) -> RuntimeLeakReport:
        if self.committed:
            raise PluginRuntimeTransactionError(
                "Committed runtime transaction cannot be rolled back"
            )
        if self.rolled_back:
            return self.leak_report()

        await self.host.deactivate(self.manifest.plugin_key)
        self.rolled_back = True
        report = self.leak_report()
        if not report.clean:
            raise PluginRuntimeTransactionError(
                "Runtime rollback left registered resources: "
                f"modules={report.module_names}, "
                f"adapter={report.adapter_present}, "
                f"registry={report.registry_present}, "
                f"manager={report.manager_present}"
            )
        return report

    def leak_report(self) -> RuntimeLeakReport:
        key = self.manifest.plugin_key
        module_prefix = (
            f"shieldnet_plugin_{key.replace('-', '_')}_"
        )
        module_names = tuple(
            sorted(
                name for name in sys.modules
                if name.startswith(module_prefix)
            )
        )

        try:
            self.host.registry.get(key)
            registry_present = True
        except Exception:
            registry_present = False

        try:
            self.host.manager.get(key)
            manager_present = True
        except Exception:
            manager_present = False

        return RuntimeLeakReport(
            plugin_key=key,
            module_names=module_names,
            adapter_present=key in self.host._adapters,
            registry_present=registry_present,
            manager_present=manager_present,
        )

    async def _cleanup_failed_prepare(self) -> None:
        try:
            await self.host.deactivate(self.manifest.plugin_key)
        except Exception as exc:
            raise PluginRuntimeHostError(
                "Runtime prepare failed and cleanup also failed: "
                f"{exc}"
            ) from exc


def runtime_transaction(
    host: PluginRuntimeHost,
    *,
    manifest: PluginManifest,
    plugin_root: Path,
    configuration: dict[str, Any] | None = None,
    services: dict[str, Any] | None = None,
) -> PluginRuntimeTransaction:
    return PluginRuntimeTransaction(
        host,
        manifest=manifest,
        plugin_root=plugin_root,
        configuration=configuration,
        services=services,
    )
