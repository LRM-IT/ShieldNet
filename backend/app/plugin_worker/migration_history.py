from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugin_migrations import PluginMigrationRecord


class PluginMigrationHistoryError(RuntimeError):
    """Raised when persisted migration history is inconsistent."""


@dataclass(frozen=True)
class InstalledMigrationHistory:
    plugin_key: str
    checksums: Mapping[str, str]
    records: tuple[PluginMigrationRecord, ...]


async def load_installed_migration_history(
    session: AsyncSession,
    *,
    plugin_key: str,
) -> InstalledMigrationHistory:
    """
    Load successfully applied migrations for one plugin.

    Failed, rolled-back or dry-run records are intentionally ignored.
    """
    result = await session.execute(
        select(PluginMigrationRecord)
        .where(
            PluginMigrationRecord.plugin_key == plugin_key,
            PluginMigrationRecord.status == "applied",
        )
        .order_by(
            PluginMigrationRecord.migration_order.asc(),
            PluginMigrationRecord.migration_filename.asc(),
        )
    )

    records = tuple(result.scalars().all())
    checksums: dict[str, str] = {}
    seen_orders: dict[int, str] = {}

    for record in records:
        existing = checksums.get(record.migration_filename)
        if existing is not None and existing != record.checksum_sha256:
            raise PluginMigrationHistoryError(
                "Conflicting checksums recorded for "
                f"{plugin_key}/{record.migration_filename}"
            )

        existing_filename = seen_orders.get(record.migration_order)
        if (
            existing_filename is not None
            and existing_filename != record.migration_filename
        ):
            raise PluginMigrationHistoryError(
                "Conflicting migration order recorded for "
                f"{plugin_key}: {record.migration_order:04d}"
            )

        checksums[record.migration_filename] = record.checksum_sha256
        seen_orders[record.migration_order] = record.migration_filename

    return InstalledMigrationHistory(
        plugin_key=plugin_key,
        checksums=checksums,
        records=records,
    )
