from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugins import (
    GuildPluginInstallation,
    PluginInstalledVersion,
    PluginInstallJob,
    PluginInstallLog,
    PluginRegistry,
    PluginRuntimeEvent,
    PluginRuntimeInstance,
    PluginRuntimeState,
)
from app.plugin_worker.runtime_host import runtime_host
from app.plugins.manifest import PluginManifest

PLUGIN_ROOT = Path("/opt/shieldnet/plugins").resolve()
REMOVE_ROOT = Path("/opt/shieldnet/plugin-runtime/removing").resolve()


class PluginLifecycleError(RuntimeError):
    """Raised when plugin removal cannot be completed safely."""


def _plugin_path(plugin_key: str) -> Path:
    key = plugin_key.strip().lower()
    path = (PLUGIN_ROOT / key).resolve()
    if not key or path.parent != PLUGIN_ROOT:
        raise PluginLifecycleError("Invalid plugin key or plugin path")
    return path


async def uninstall_plugin(
    session: AsyncSession,
    *,
    job: PluginInstallJob,
) -> None:
    key = job.plugin_key.strip().lower()
    target = _plugin_path(key)
    removed_path = (REMOVE_ROOT / f"{key}-{job.id}").resolve()
    if removed_path.parent != REMOVE_ROOT:
        raise PluginLifecycleError("Invalid removal staging path")

    installed = (
        await session.execute(
            select(PluginInstalledVersion).where(
                PluginInstalledVersion.plugin_key == key
            )
        )
    ).scalar_one_or_none()
    registry = (
        await session.execute(
            select(PluginRegistry).where(PluginRegistry.plugin_key == key)
        )
    ).scalar_one_or_none()

    if installed is None and registry is None and not target.exists():
        raise PluginLifecycleError(f"Plugin is not installed: {key}")

    manifest = None
    manifest_path = target / "plugin.json"
    if manifest_path.is_file():
        manifest = PluginManifest.from_path(manifest_path)

    job.status = "stopping"
    job.progress = 25
    session.add(
        PluginInstallLog(
            job_id=job.id,
            level="info",
            message="plugin runtime stop started",
            metadata_json={"plugin_key": key},
        )
    )
    await session.commit()

    await runtime_host.deactivate(key)

    job.status = "removing"
    job.progress = 55
    session.add(
        PluginInstallLog(
            job_id=job.id,
            level="info",
            message="plugin runtime stopped; filesystem removal started",
            metadata_json={"plugin_key": key},
        )
    )
    await session.commit()

    REMOVE_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(removed_path, ignore_errors=True)
    moved = False
    if target.exists():
        target.rename(removed_path)
        moved = True

    try:
        now = datetime.now(timezone.utc)
        await session.execute(
            delete(PluginRuntimeInstance).where(
                PluginRuntimeInstance.plugin_key == key
            )
        )
        await session.execute(
            delete(GuildPluginInstallation).where(
                GuildPluginInstallation.plugin_key == key
            )
        )
        await session.execute(
            delete(PluginRuntimeState).where(
                PluginRuntimeState.plugin_key == key
            )
        )
        await session.execute(
            delete(PluginInstalledVersion).where(
                PluginInstalledVersion.plugin_key == key
            )
        )
        await session.execute(
            delete(PluginRegistry).where(PluginRegistry.plugin_key == key)
        )

        session.add(
            PluginRuntimeEvent(
                plugin_key=key,
                job_id=job.id,
                event_type="plugin_uninstalled",
                message="Plugin runtime, files and installation records removed",
                metadata_json={
                    "removed_path": str(target),
                    "removed_at": now.isoformat(),
                },
            )
        )
        job.status = "installed"
        job.progress = 100
        job.error = None
        job.finished_at = now
        session.add(
            PluginInstallLog(
                job_id=job.id,
                level="info",
                message="plugin uninstallation completed",
                metadata_json={"progress": 100},
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()
        if moved and removed_path.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            removed_path.rename(target)
        if manifest is not None and target.exists():
            try:
                await runtime_host.activate(
                    manifest=manifest,
                    plugin_root=target,
                )
            except Exception:
                pass
        raise
    else:
        if moved:
            shutil.rmtree(removed_path, ignore_errors=True)
