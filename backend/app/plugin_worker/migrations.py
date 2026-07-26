from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


_MIGRATION_NAME_RE = re.compile(
    r"^(?P<order>[0-9]{4})_(?P<name>[a-z0-9][a-z0-9_-]{0,119})\.sql$"
)


class PluginMigrationError(ValueError):
    """Raised when a plugin migration directory is invalid."""


@dataclass(frozen=True, order=True)
class PluginMigration:
    order: int
    name: str
    filename: str
    path: Path
    checksum_sha256: str
    size_bytes: int


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def discover_migrations(
    plugin_root: Path,
    *,
    max_file_bytes: int = 2 * 1024 * 1024,
) -> tuple[PluginMigration, ...]:
    """
    Discover and validate SQL migration files without executing them.

    Expected layout:

        plugin_root/
            migrations/
                0001_initial.sql
                0002_add_indexes.sql

    This function performs no database operations.
    """
    plugin_root = plugin_root.resolve()
    migrations_root = plugin_root / "migrations"

    if not plugin_root.is_dir():
        raise PluginMigrationError(
            f"Plugin directory does not exist: {plugin_root}"
        )

    if not migrations_root.exists():
        return ()

    if not migrations_root.is_dir():
        raise PluginMigrationError(
            f"Plugin migrations path is not a directory: {migrations_root}"
        )

    discovered: list[PluginMigration] = []
    seen_orders: set[int] = set()
    seen_names: set[str] = set()

    for path in sorted(migrations_root.iterdir(), key=lambda item: item.name):
        if path.is_dir():
            raise PluginMigrationError(
                f"Nested migration directories are not supported: {path.name}"
            )

        if not path.is_file():
            raise PluginMigrationError(
                f"Unsupported migration entry: {path.name}"
            )

        match = _MIGRATION_NAME_RE.fullmatch(path.name)
        if match is None:
            raise PluginMigrationError(
                "Migration filename must use "
                "'NNNN_lowercase_name.sql': "
                f"{path.name}"
            )

        order = int(match.group("order"))
        name = match.group("name")

        if order == 0:
            raise PluginMigrationError(
                f"Migration order must start from 0001: {path.name}"
            )
        if order in seen_orders:
            raise PluginMigrationError(
                f"Duplicate migration order {order:04d}"
            )
        if name in seen_names:
            raise PluginMigrationError(
                f"Duplicate migration name: {name}"
            )

        size_bytes = path.stat().st_size
        if size_bytes == 0:
            raise PluginMigrationError(
                f"Migration file is empty: {path.name}"
            )
        if size_bytes > max_file_bytes:
            raise PluginMigrationError(
                f"Migration file exceeds {max_file_bytes} bytes: {path.name}"
            )

        try:
            sql = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise PluginMigrationError(
                f"Migration must be UTF-8 encoded: {path.name}"
            ) from exc

        if "\x00" in sql:
            raise PluginMigrationError(
                f"Migration contains a NUL byte: {path.name}"
            )

        seen_orders.add(order)
        seen_names.add(name)
        discovered.append(
            PluginMigration(
                order=order,
                name=name,
                filename=path.name,
                path=path,
                checksum_sha256=file_checksum(path),
                size_bytes=size_bytes,
            )
        )

    discovered.sort(key=lambda item: item.order)

    for expected, migration in enumerate(discovered, start=1):
        if migration.order != expected:
            raise PluginMigrationError(
                "Migration sequence must be contiguous starting at 0001; "
                f"expected {expected:04d}, found {migration.order:04d}"
            )

    return tuple(discovered)
