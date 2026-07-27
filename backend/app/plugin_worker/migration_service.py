from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.plugin_worker.migration_history import (
    InstalledMigrationHistory,
    load_installed_migration_history,
)
from app.plugin_worker.migration_preflight import (
    PluginMigrationPreflight,
    run_migration_preflight,
)
from app.plugin_worker.migration_runner import (
    MigrationDryRunResult,
    PluginMigrationDryRunner,
)


@dataclass(frozen=True)
class PluginMigrationDryRunReport:
    history: InstalledMigrationHistory
    preflight: PluginMigrationPreflight
    execution: MigrationDryRunResult

    @property
    def plugin_key(self) -> str:
        return self.preflight.plugin_key

    @property
    def applied_count(self) -> int:
        return len(self.history.checksums)

    @property
    def pending_count(self) -> int:
        return len(self.preflight.pending)


class PluginMigrationService:
    """
    Coordinate DB-backed preflight and transactional dry-run execution.

    This service never commits plugin SQL and never writes migration history.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        statement_timeout_ms: int = 30_000,
        lock_timeout_ms: int = 5_000,
    ) -> None:
        self.runner = PluginMigrationDryRunner(
            engine,
            statement_timeout_ms=statement_timeout_ms,
            lock_timeout_ms=lock_timeout_ms,
        )

    async def dry_run(
        self,
        session: AsyncSession,
        *,
        plugin_root: Path,
        plugin_key: str,
    ) -> PluginMigrationDryRunReport:
        history = await load_installed_migration_history(
            session,
            plugin_key=plugin_key,
        )

        preflight = run_migration_preflight(
            plugin_root,
            plugin_key=plugin_key,
            installed_checksums=history.checksums,
        )

        execution = await self.runner.run(preflight)

        return PluginMigrationDryRunReport(
            history=history,
            preflight=preflight,
            execution=execution,
        )
