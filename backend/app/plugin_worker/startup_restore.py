from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugins import (
    PluginInstalledVersion,
    PluginRegistry,
    PluginRuntimeEvent,
    PluginRuntimeState,
)
from app.plugin_worker.activation import directory_checksum
from app.plugin_worker.runtime_host import runtime_host
from app.plugin_worker.runtime_transaction import runtime_transaction
from app.plugins.manifest import PluginManifest


class PluginStartupRestoreError(RuntimeError):
    """Raised when an installed plugin cannot be restored at startup."""


@dataclass(frozen=True)
class PluginStartupRestoreReport:
    plugin_key: str
    version: str
    action: str
    healthy: bool
    error: str | None = None


def _validated_install_path(value: str) -> Path:
    root = Path("/opt/shieldnet/plugins").resolve()
    path = Path(value).resolve()
    if path != root and root not in path.parents:
        raise PluginStartupRestoreError(
            f"Installed plugin path escapes plugin root: {path}"
        )
    if not path.is_dir():
        raise PluginStartupRestoreError(
            f"Installed plugin directory does not exist: {path}"
        )
    return path


async def restore_active_plugin_runtimes(
    session: AsyncSession,
) -> tuple[PluginStartupRestoreReport, ...]:
    rows = (
        await session.execute(
            select(PluginInstalledVersion, PluginRegistry)
            .join(
                PluginRegistry,
                PluginRegistry.plugin_key
                == PluginInstalledVersion.plugin_key,
            )
            .where(
                PluginInstalledVersion.active.is_(True),
                PluginRegistry.enabled.is_(True),
            )
            .order_by(PluginInstalledVersion.plugin_key.asc())
        )
    ).all()

    reports: list[PluginStartupRestoreReport] = []

    for installed, registry in rows:
        key = installed.plugin_key.strip().lower()
        version = installed.version

        try:
            install_path = _validated_install_path(installed.install_path)
            manifest_path = install_path / "plugin.json"
            if not manifest_path.is_file():
                raise PluginStartupRestoreError(
                    f"Installed manifest is missing: {manifest_path}"
                )

            manifest = PluginManifest.from_path(manifest_path)
            if manifest.plugin_key != key:
                raise PluginStartupRestoreError(
                    "Installed manifest plugin key does not match database"
                )
            if manifest.version != version:
                raise PluginStartupRestoreError(
                    "Installed manifest version does not match database"
                )

            actual_checksum = directory_checksum(install_path)
            expected_checksum = installed.checksum_sha256
            if expected_checksum and actual_checksum != expected_checksum:
                raise PluginStartupRestoreError(
                    "Installed plugin checksum does not match database"
                )

            try:
                await runtime_host.deactivate(key)
            except Exception:
                pass

            transaction = runtime_transaction(
                runtime_host,
                manifest=manifest,
                plugin_root=install_path,
            )
            await transaction.prepare()
            activation = await transaction.commit()

            now = datetime.now(timezone.utc)
            registry.healthy = True
            registry.last_error = None
            registry.version = manifest.version
            registry.manifest_path = str(manifest_path)
            registry.manifest = manifest.raw
            registry.checksum = actual_checksum
            registry.updated_at = now

            state = (
                await session.execute(
                    select(PluginRuntimeState).where(
                        PluginRuntimeState.plugin_key == key
                    )
                )
            ).scalar_one_or_none()
            if state is not None:
                state.prepared_version = manifest.version
                state.package_path = str(install_path)
                state.manifest_json = manifest.raw
                state.state = "running"
                state.last_error = None
                state.updated_at = now

            session.add(
                PluginRuntimeEvent(
                    plugin_key=key,
                    job_id=state.last_job_id if state else None,
                    event_type="runtime_restored",
                    message="Plugin runtime restored during worker startup",
                    metadata_json={
                        "version": manifest.version,
                        "path": str(install_path),
                        "health": activation.snapshot.health,
                    },
                )
            )
            await session.commit()

            reports.append(
                PluginStartupRestoreReport(
                    plugin_key=key,
                    version=version,
                    action="runtime_restored",
                    healthy=True,
                )
            )
        except Exception as exc:
            await session.rollback()
            error = str(exc)[:4000]
            now = datetime.now(timezone.utc)

            current_registry = (
                await session.execute(
                    select(PluginRegistry).where(
                        PluginRegistry.plugin_key == key
                    )
                )
            ).scalar_one_or_none()
            if current_registry is not None:
                current_registry.healthy = False
                current_registry.last_error = error
                current_registry.updated_at = now

            state = (
                await session.execute(
                    select(PluginRuntimeState).where(
                        PluginRuntimeState.plugin_key == key
                    )
                )
            ).scalar_one_or_none()
            if state is not None:
                state.state = "failed"
                state.last_error = error
                state.updated_at = now

            session.add(
                PluginRuntimeEvent(
                    plugin_key=key,
                    job_id=state.last_job_id if state else None,
                    event_type="runtime_restore_failed",
                    message="Plugin runtime restore failed during startup",
                    metadata_json={
                        "version": version,
                        "error": error,
                    },
                )
            )
            await session.commit()

            reports.append(
                PluginStartupRestoreReport(
                    plugin_key=key,
                    version=version,
                    action="runtime_restore_failed",
                    healthy=False,
                    error=error,
                )
            )

    return tuple(reports)
