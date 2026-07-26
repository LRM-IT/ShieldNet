from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Sequence

from app.plugin_worker.migrations import PluginMigration


class MigrationPlanStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    CHECKSUM_MISMATCH = "checksum_mismatch"


@dataclass(frozen=True)
class MigrationPlanItem:
    order: int
    filename: str
    checksum_sha256: str
    status: MigrationPlanStatus
    installed_checksum_sha256: str | None = None


class PluginMigrationPlanError(ValueError):
    """Raised when installed migration metadata is internally inconsistent."""


def build_migration_plan(
    migrations: Sequence[PluginMigration],
    installed_checksums: Mapping[str, str],
) -> tuple[MigrationPlanItem, ...]:
    """
    Build a read-only migration plan.

    `installed_checksums` maps migration filename to its recorded SHA-256.
    This function performs no database operations and never executes SQL.
    """
    discovered_names = {migration.filename for migration in migrations}

    unknown_installed = sorted(
        filename
        for filename in installed_checksums
        if filename not in discovered_names
    )
    if unknown_installed:
        raise PluginMigrationPlanError(
            "Installed migration records are missing from the package: "
            + ", ".join(unknown_installed)
        )

    plan: list[MigrationPlanItem] = []

    for migration in migrations:
        installed_checksum = installed_checksums.get(migration.filename)

        if installed_checksum is None:
            status = MigrationPlanStatus.PENDING
        elif installed_checksum == migration.checksum_sha256:
            status = MigrationPlanStatus.APPLIED
        else:
            status = MigrationPlanStatus.CHECKSUM_MISMATCH

        plan.append(
            MigrationPlanItem(
                order=migration.order,
                filename=migration.filename,
                checksum_sha256=migration.checksum_sha256,
                status=status,
                installed_checksum_sha256=installed_checksum,
            )
        )

    return tuple(plan)


def assert_migration_plan_safe(
    plan: Sequence[MigrationPlanItem],
) -> None:
    """
    Reject plans containing modified already-applied migrations.

    Pending migrations are allowed. Applied migrations are allowed.
    """
    mismatches = [
        item.filename
        for item in plan
        if item.status is MigrationPlanStatus.CHECKSUM_MISMATCH
    ]

    if mismatches:
        raise PluginMigrationPlanError(
            "Applied migration checksum mismatch: "
            + ", ".join(mismatches)
        )


def pending_migrations(
    migrations: Sequence[PluginMigration],
    plan: Sequence[MigrationPlanItem],
) -> tuple[PluginMigration, ...]:
    """Return pending migrations while preserving validated order."""
    status_by_filename = {
        item.filename: item.status
        for item in plan
    }

    return tuple(
        migration
        for migration in migrations
        if status_by_filename.get(migration.filename)
        is MigrationPlanStatus.PENDING
    )
