from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugins import (
    PluginInstallJob,
    PluginInstallLog,
    PluginInstalledVersion,
    PluginRegistry,
    PluginRuntimeEvent,
    PluginRuntimeState,
)
from app.plugin_worker.migration_preflight import (
    PluginMigrationPreflight,
    run_migration_preflight,
)
from app.plugins.manifest import PluginManifest


PLUGIN_ROOT = Path("/opt/shieldnet/plugins")
BACKUP_ROOT = Path("/opt/shieldnet/plugin-runtime/backups")


class PluginActivationError(RuntimeError):
    """Raised when a validated plugin package cannot be activated."""


@dataclass(frozen=True)
class PluginActivationResult:
    plugin_key: str
    version: str
    install_path: Path
    backup_path: Path | None
    checksum_sha256: str


def directory_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with item.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


class PluginActivator:
    """Activate a validated package without running migrations or reloading services."""

    async def activate(
        self,
        session: AsyncSession,
        *,
        job: PluginInstallJob,
        validated_path: Path,
    ) -> PluginActivationResult:
        validated_path = validated_path.resolve()
        manifest_path = validated_path / "plugin.json"

        if not validated_path.is_dir():
            raise PluginActivationError(
                f"Validated plugin directory does not exist: {validated_path}"
            )
        if not manifest_path.is_file():
            raise PluginActivationError(
                f"Validated plugin manifest is missing: {manifest_path}"
            )

        manifest = PluginManifest.from_path(manifest_path)
        if manifest.plugin_key != job.plugin_key:
            raise PluginActivationError(
                "Validated package plugin key does not match installation job"
            )

        preflight = await self._run_migration_preflight(
            session,
            job=job,
            manifest=manifest,
            validated_path=validated_path,
        )

        target = PLUGIN_ROOT / manifest.plugin_key
        temporary = PLUGIN_ROOT / f".{manifest.plugin_key}.installing-{job.id}"
        backup = await self._backup_existing(
            session,
            plugin_key=manifest.plugin_key,
            target=target,
        )

        try:
            await self._set_job_status(
                session,
                job=job,
                status="installing",
                progress=82,
                message="plugin activation started",
            )

            PLUGIN_ROOT.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(temporary, ignore_errors=True)
            shutil.copytree(validated_path, temporary)

            copied_manifest = PluginManifest.from_path(temporary / "plugin.json")
            if copied_manifest.plugin_key != manifest.plugin_key:
                raise PluginActivationError("Copied package plugin key mismatch")
            if copied_manifest.version != manifest.version:
                raise PluginActivationError("Copied package version mismatch")

            if target.exists():
                shutil.rmtree(target)
            os.replace(temporary, target)

            checksum = directory_checksum(target)
            await self._record_installation(
                session,
                job=job,
                manifest=manifest,
                install_path=target,
                backup_path=backup,
                checksum_sha256=checksum,
                preflight=preflight,
            )

            return PluginActivationResult(
                plugin_key=manifest.plugin_key,
                version=manifest.version,
                install_path=target,
                backup_path=backup,
                checksum_sha256=checksum,
            )
        except Exception as exc:
            await session.rollback()
            shutil.rmtree(temporary, ignore_errors=True)
            if backup is not None and backup.exists():
                shutil.rmtree(target, ignore_errors=True)
                shutil.copytree(backup, target)
            if isinstance(exc, PluginActivationError):
                raise
            raise PluginActivationError(str(exc)) from exc

    async def _run_migration_preflight(
        self,
        session: AsyncSession,
        *,
        job: PluginInstallJob,
        manifest: PluginManifest,
        validated_path: Path,
    ) -> PluginMigrationPreflight:
        try:
            result = run_migration_preflight(
                validated_path,
                plugin_key=manifest.plugin_key,
            )
        except Exception as exc:
            raise PluginActivationError(
                f"Plugin migration preflight failed: {exc}"
            ) from exc

        session.add(
            PluginInstallLog(
                job_id=job.id,
                level="info",
                message="plugin migration preflight passed",
                metadata_json={
                    "schema": result.schema_name,
                    "migration_count": len(result.migrations),
                    "pending_count": len(result.pending),
                    "execution": "disabled",
                },
            )
        )
        await session.commit()
        return result

    async def _backup_existing(
        self,
        session: AsyncSession,
        *,
        plugin_key: str,
        target: Path,
    ) -> Path | None:
        if not target.exists():
            return None

        installed = (
            await session.execute(
                select(PluginInstalledVersion).where(
                    PluginInstalledVersion.plugin_key == plugin_key
                )
            )
        ).scalar_one_or_none()

        version = installed.version if installed is not None else "unknown"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = BACKUP_ROOT / plugin_key / f"{version}-{stamp}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, backup)
        return backup

    async def _record_installation(
        self,
        session: AsyncSession,
        *,
        job: PluginInstallJob,
        manifest: PluginManifest,
        install_path: Path,
        backup_path: Path | None,
        checksum_sha256: str,
        preflight: PluginMigrationPreflight,
    ) -> None:
        now = datetime.now(timezone.utc)

        installed = (
            await session.execute(
                select(PluginInstalledVersion).where(
                    PluginInstalledVersion.plugin_key == manifest.plugin_key
                )
            )
        ).scalar_one_or_none()
        previous_version = installed.version if installed is not None else None

        await session.execute(
            insert(PluginInstalledVersion)
            .values(
                plugin_key=manifest.plugin_key,
                version=manifest.version,
                previous_version=previous_version,
                install_path=str(install_path),
                checksum_sha256=checksum_sha256,
                active=True,
                installed_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[PluginInstalledVersion.plugin_key],
                set_={
                    "version": manifest.version,
                    "previous_version": previous_version,
                    "install_path": str(install_path),
                    "checksum_sha256": checksum_sha256,
                    "active": True,
                    "updated_at": now,
                },
            )
        )

        registry = (
            await session.execute(
                select(PluginRegistry).where(
                    PluginRegistry.plugin_key == manifest.plugin_key
                )
            )
        ).scalar_one_or_none()

        if registry is None:
            registry = PluginRegistry(
                plugin_key=manifest.plugin_key,
                name=manifest.name,
                version=manifest.version,
                manifest_path=str(install_path / "plugin.json"),
            )
            session.add(registry)

        registry.name = manifest.name
        registry.version = manifest.version
        registry.description = manifest.description
        registry.author = manifest.author
        registry.min_core_version = manifest.min_core_version
        registry.manifest_path = str(install_path / "plugin.json")
        registry.manifest = manifest.raw
        registry.checksum = checksum_sha256
        registry.enabled = False
        registry.healthy = True
        registry.last_error = None

        await session.execute(
            insert(PluginRuntimeState)
            .values(
                plugin_key=manifest.plugin_key,
                prepared_version=manifest.version,
                package_path=str(install_path),
                manifest_json=manifest.raw,
                state="installed",
                last_job_id=job.id,
                last_error=None,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[PluginRuntimeState.plugin_key],
                set_={
                    "prepared_version": manifest.version,
                    "package_path": str(install_path),
                    "manifest_json": manifest.raw,
                    "state": "installed",
                    "last_job_id": job.id,
                    "last_error": None,
                    "updated_at": now,
                },
            )
        )

        job.status = "installed"
        job.progress = 90

        session.add(
            PluginInstallLog(
                job_id=job.id,
                level="info",
                message="plugin package activated",
                metadata_json={
                    "version": manifest.version,
                    "path": str(install_path),
                    "backup": str(backup_path) if backup_path else None,
                    "migration_count": len(preflight.migrations),
                    "pending_migration_count": len(preflight.pending),
                    "migration_schema": preflight.schema_name,
                    "migration_execution": "disabled",
                },
            )
        )
        session.add(
            PluginRuntimeEvent(
                plugin_key=manifest.plugin_key,
                job_id=job.id,
                event_type="plugin_activated",
                message="Plugin package activated",
                metadata_json={
                    "version": manifest.version,
                    "path": str(install_path),
                },
            )
        )
        await session.commit()

    async def _set_job_status(
        self,
        session: AsyncSession,
        *,
        job: PluginInstallJob,
        status: str,
        progress: int,
        message: str,
    ) -> None:
        job.status = status
        job.progress = progress
        session.add(
            PluginInstallLog(
                job_id=job.id,
                level="info",
                message=message,
                metadata_json={"status": status, "progress": progress},
            )
        )
        await session.commit()
