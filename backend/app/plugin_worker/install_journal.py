from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugins import PluginInstallJob, PluginInstallLog, PluginRuntimeEvent

JOURNAL_ROOT = Path("/opt/shieldnet/plugin-runtime/install-journal")


class PluginInstallJournalError(RuntimeError):
    pass


@dataclass(frozen=True)
class PluginRecoveryReport:
    journal_path: Path
    plugin_key: str
    stage: str
    action: str
    job_id: UUID | None
    error: str | None = None


class PluginInstallJournal:
    def __init__(self, path: Path, payload: dict[str, Any]) -> None:
        self.path = path
        self.payload = payload

    @classmethod
    def begin(
        cls,
        *,
        job_id: UUID,
        plugin_key: str,
        candidate_version: str,
        target_path: Path,
        temporary_path: Path,
        backup_path: Path | None,
    ) -> "PluginInstallJournal":
        JOURNAL_ROOT.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "schema": 1,
            "job_id": str(job_id),
            "plugin_key": plugin_key,
            "candidate_version": candidate_version,
            "target_path": str(target_path),
            "temporary_path": str(temporary_path),
            "backup_path": str(backup_path) if backup_path else None,
            "displaced_path": None,
            "stage": "prepared",
            "created_at": now,
            "updated_at": now,
            "error": None,
        }
        journal = cls(JOURNAL_ROOT / f"{job_id}.json", payload)
        journal._write()
        return journal

    def set_displaced_path(self, path: Path) -> None:
        self.payload["displaced_path"] = str(path)
        self.payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write()

    def advance(self, stage: str) -> None:
        self.payload["stage"] = stage
        self.payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write()

    def fail(self, error: str) -> None:
        self.payload["stage"] = "rollback"
        self.payload["error"] = error[:4000]
        self.payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write()

    def complete(self) -> None:
        self.path.unlink(missing_ok=True)
        self._fsync_directory(self.path.parent)

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self.payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        self._fsync_directory(self.path.parent)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        try:
            descriptor = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _safe_path(value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise PluginInstallJournalError(f"Invalid journal field: {field}")
    path = Path(value).resolve()
    roots = (
        Path("/opt/shieldnet/plugins").resolve(),
        Path("/opt/shieldnet/plugin-runtime").resolve(),
    )
    if not any(path == root or root in path.parents for root in roots):
        raise PluginInstallJournalError(f"Journal path escapes ShieldNet roots: {path}")
    return path


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise PluginInstallJournalError(f"Unsupported install journal: {path}")
    return payload


def _restore_files(payload: dict[str, Any]) -> str:
    target = _safe_path(payload.get("target_path"), "target_path")
    temporary = _safe_path(payload.get("temporary_path"), "temporary_path")
    backup_raw = payload.get("backup_path")
    backup = _safe_path(backup_raw, "backup_path") if backup_raw else None
    displaced_raw = payload.get("displaced_path")
    displaced = (
        _safe_path(displaced_raw, "displaced_path")
        if displaced_raw
        else None
    )
    shutil.rmtree(temporary, ignore_errors=True)

    if displaced is not None and displaced.is_dir():
        shutil.rmtree(target, ignore_errors=True)
        os.replace(displaced, target)
        PluginInstallJournal._fsync_directory(target.parent)
        return "displaced_directory_restored"

    if backup is not None and backup.is_dir():
        shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(backup, target)
        return "previous_files_restored"

    shutil.rmtree(target, ignore_errors=True)
    return "incomplete_new_install_removed"


async def recover_install_journals(
    session: AsyncSession,
) -> tuple[PluginRecoveryReport, ...]:
    JOURNAL_ROOT.mkdir(parents=True, exist_ok=True)
    reports: list[PluginRecoveryReport] = []

    for path in sorted(JOURNAL_ROOT.glob("*.json")):
        try:
            payload = _load(path)
            plugin_key = str(payload.get("plugin_key") or "").strip().lower()
            stage = str(payload.get("stage") or "unknown")
            raw_job_id = payload.get("job_id")
            job_id = UUID(str(raw_job_id)) if raw_job_id else None
            job = None
            if job_id is not None:
                job = (
                    await session.execute(
                        select(PluginInstallJob).where(PluginInstallJob.id == job_id)
                    )
                ).scalar_one_or_none()

            now = datetime.now(timezone.utc)
            if stage == "database_committed":
                action = "committed_install_finalized"
                if job is not None:
                    job.status = "installed"
                    job.progress = 100
                    job.error = None
                    job.finished_at = now
                    session.add(PluginInstallLog(
                        job_id=job.id,
                        level="warning",
                        message="installation finalized during startup recovery",
                        metadata_json={"recovered_stage": stage, "progress": 100},
                    ))
                    session.add(PluginRuntimeEvent(
                        plugin_key=plugin_key,
                        job_id=job.id,
                        event_type="install_recovery_finalized",
                        message="Committed installation finalized during startup recovery",
                        metadata_json={"recovered_stage": stage},
                    ))
            else:
                action = _restore_files(payload)
                if job is not None:
                    error = (
                        "installation interrupted before database commit; "
                        f"startup recovery action: {action}"
                    )
                    job.status = "failed"
                    job.error = error
                    job.finished_at = now
                    session.add(PluginInstallLog(
                        job_id=job.id,
                        level="error",
                        message="interrupted installation recovered",
                        metadata_json={"recovered_stage": stage, "action": action},
                    ))
                    session.add(PluginRuntimeEvent(
                        plugin_key=plugin_key,
                        job_id=job.id,
                        event_type="install_recovery_rolled_back",
                        message="Interrupted installation rolled back during startup",
                        metadata_json={"recovered_stage": stage, "action": action},
                    ))

            await session.commit()
            path.unlink(missing_ok=True)
            PluginInstallJournal._fsync_directory(path.parent)
            reports.append(PluginRecoveryReport(
                journal_path=path,
                plugin_key=plugin_key,
                stage=stage,
                action=action,
                job_id=job_id,
            ))
        except Exception as exc:
            await session.rollback()
            reports.append(PluginRecoveryReport(
                journal_path=path,
                plugin_key="unknown",
                stage="unknown",
                action="recovery_failed",
                job_id=None,
                error=str(exc),
            ))

    return tuple(reports)
