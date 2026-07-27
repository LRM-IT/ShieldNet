from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from app.plugin_worker.migration_plan import (
    MigrationPlanItem,
    assert_migration_plan_safe,
    build_migration_plan,
    pending_migrations,
)
from app.plugin_worker.migration_policy import (
    required_schema_prefix,
    validate_migration_policy,
    validate_schema_scope,
)
from app.plugin_worker.migrations import (
    PluginMigration,
    discover_migrations,
)


@dataclass(frozen=True)
class PluginMigrationPreflight:
    plugin_key: str
    plugin_root: Path
    schema_name: str
    migrations: tuple[PluginMigration, ...]
    plan: tuple[MigrationPlanItem, ...]
    pending: tuple[PluginMigration, ...]

    @property
    def has_migrations(self) -> bool:
        return bool(self.migrations)

    @property
    def has_pending(self) -> bool:
        return bool(self.pending)


def run_migration_preflight(
    plugin_root: Path,
    *,
    plugin_key: str,
    installed_checksums: Mapping[str, str] | None = None,
    max_file_bytes: int = 2 * 1024 * 1024,
) -> PluginMigrationPreflight:
    """
    Validate plugin migrations and build a read-only execution plan.

    This function:
    - discovers migration files;
    - validates naming, order, encoding, size, and checksum;
    - enforces static SQL policy;
    - enforces plugin schema scope;
    - detects pending, applied, and changed migrations.

    It does not connect to a database and never executes SQL.
    """
    installed_checksums = installed_checksums or {}
    plugin_root = plugin_root.resolve()
    schema_name = required_schema_prefix(plugin_key)

    migrations = discover_migrations(
        plugin_root,
        max_file_bytes=max_file_bytes,
    )

    validate_migration_policy(migrations)
    validate_schema_scope(
        migrations,
        plugin_key=plugin_key,
    )

    plan = build_migration_plan(
        migrations,
        installed_checksums,
    )
    assert_migration_plan_safe(plan)

    pending = pending_migrations(
        migrations,
        plan,
    )

    return PluginMigrationPreflight(
        plugin_key=plugin_key,
        plugin_root=plugin_root,
        schema_name=schema_name,
        migrations=migrations,
        plan=plan,
        pending=pending,
    )
