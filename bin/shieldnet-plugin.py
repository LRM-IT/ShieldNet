#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT = Path("/opt/shieldnet")
BACKEND = PROJECT / "backend"
PLUGIN_ROOT = PROJECT / "plugins"
PLUGIN_SYSTEM = PROJECT / "plugin-system"
DB_OWNER = os.environ.get("SHIELDNET_DB_OWNER", "shieldnet_owner")
DB_RUNTIME = os.environ.get("SHIELDNET_DB_RUNTIME", "shieldnet_backend")


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_plugin(source: Path, target: Path, plugin_key: str) -> Path | None:
    backup = None
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = PROJECT / "backups" / "plugins" / f"{plugin_key}-{stamp}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, backup)

    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    for directory, dirnames, filenames in os.walk(target):
        os.chmod(directory, 0o750)
        for filename in filenames:
            os.chmod(Path(directory) / filename, 0o640)

    try:
        shutil.chown(target, user="shieldnet-api", group="shieldnet-api")
        for directory, dirnames, filenames in os.walk(target):
            shutil.chown(directory, user="shieldnet-api", group="shieldnet-api")
            for filename in filenames:
                shutil.chown(Path(directory) / filename, user="shieldnet-api", group="shieldnet-api")
    except LookupError:
        pass

    return backup


async def install_plugin(source: Path) -> None:
    sys.path.insert(0, str(BACKEND))

    from sqlalchemy import select
    from app.db.session import AsyncSessionFactory
    from app.models.plugins import PluginRegistry
    from app.plugins.manifest import PluginManifest

    manifest_path = source / "plugin.json"
    manifest = PluginManifest.from_path(manifest_path)

    if not manifest.supports_core("7.0.0"):
        fail(f"Plugin requires ShieldNet {manifest.min_core_version} or newer")

    print(f"Manifest validation: {manifest.plugin_key} {manifest.version} OK")

    target = PLUGIN_ROOT / manifest.plugin_key
    backup = copy_plugin(source, target, manifest.plugin_key)

    schema_name = "plugin_" + manifest.plugin_key.replace("-", "_")
    if not schema_name.replace("_", "").isalnum():
        fail("Unsafe plugin schema name")

    bootstrap_sql = f"""
BEGIN;
CREATE SCHEMA IF NOT EXISTS plugin_system AUTHORIZATION {DB_OWNER};
CREATE TABLE IF NOT EXISTS plugin_system.migrations (
    plugin_key VARCHAR(96) NOT NULL,
    migration_name VARCHAR(255) NOT NULL,
    checksum_sha256 VARCHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (plugin_key, migration_name)
);
ALTER SCHEMA plugin_system OWNER TO {DB_OWNER};
ALTER TABLE plugin_system.migrations OWNER TO {DB_OWNER};
CREATE SCHEMA IF NOT EXISTS {schema_name} AUTHORIZATION {DB_OWNER};
ALTER SCHEMA {schema_name} OWNER TO {DB_OWNER};
COMMIT;
"""
    subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-d", "shieldnet"],
        input=bootstrap_sql,
        text=True,
        check=True,
    )

    migrations = sorted((target / "migrations").glob("*.sql"))
    for migration in migrations:
        checksum = sha256(migration)

        lookup_sql = (
            "SELECT checksum_sha256 FROM plugin_system.migrations "
            f"WHERE plugin_key={json.dumps(manifest.plugin_key)} "
            f"AND migration_name={json.dumps(migration.name)};"
        )
        result = subprocess.run(
            ["sudo", "-u", "postgres", "psql", "-At", "-v", "ON_ERROR_STOP=1", "-d", "shieldnet"],
            input=lookup_sql,
            text=True,
            capture_output=True,
            check=True,
        )
        existing = result.stdout.strip()

        if existing:
            if existing != checksum:
                fail(f"Migration checksum mismatch: {migration.name}")
            print(f"Migration already applied: {migration.name}")
            continue

        sql = migration.read_text(encoding="utf-8")
        migration_sql = f"""
BEGIN;
SET ROLE {DB_OWNER};
{sql}
RESET ROLE;
INSERT INTO plugin_system.migrations(plugin_key,migration_name,checksum_sha256)
VALUES ({json.dumps(manifest.plugin_key)}, {json.dumps(migration.name)}, {json.dumps(checksum)});
COMMIT;
"""
        print(f"Applying migration: {migration.name}")
        subprocess.run(
            ["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-d", "shieldnet"],
            input=migration_sql,
            text=True,
            check=True,
        )

    grants_sql = f"""
BEGIN;
GRANT USAGE ON SCHEMA {schema_name} TO {DB_RUNTIME};
GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA {schema_name}
TO {DB_RUNTIME};
GRANT USAGE, SELECT, UPDATE
ON ALL SEQUENCES IN SCHEMA {schema_name}
TO {DB_RUNTIME};
ALTER DEFAULT PRIVILEGES FOR ROLE {DB_OWNER} IN SCHEMA {schema_name}
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {DB_RUNTIME};
ALTER DEFAULT PRIVILEGES FOR ROLE {DB_OWNER} IN SCHEMA {schema_name}
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {DB_RUNTIME};
GRANT USAGE ON SCHEMA plugin_system TO {DB_RUNTIME};
GRANT SELECT ON plugin_system.migrations TO {DB_RUNTIME};
COMMIT;
"""
    subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-d", "shieldnet"],
        input=grants_sql,
        text=True,
        check=True,
    )

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(PluginRegistry).where(
                PluginRegistry.plugin_key == manifest.plugin_key
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = PluginRegistry(
                plugin_key=manifest.plugin_key,
                name=manifest.name,
                version=manifest.version,
                description=manifest.description,
                manifest_path=str(target / "plugin.json"),
                enabled=True,
                healthy=True,
            )
            session.add(row)
        else:
            row.name = manifest.name
            row.version = manifest.version
            row.description = manifest.description
            row.manifest_path = str(target / "plugin.json")
            row.enabled = True
            row.healthy = True
            row.last_error = None
        await session.commit()

    print("Plugin registry: enabled")

    service = None
    for candidate in ("shieldnet-backend.service", "shieldnet-api.service"):
        check = subprocess.run(
            ["systemctl", "cat", candidate],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if check.returncode == 0:
            service = candidate
            break

    if service:
        subprocess.run(["systemctl", "restart", service], check=True)
        check = subprocess.run(["systemctl", "is-active", "--quiet", service])
        if check.returncode != 0:
            subprocess.run(["systemctl", "status", service, "--no-pager", "-l"])
            fail(f"{service} failed after restart")

    print(f"Plugin installed: {manifest.plugin_key} {manifest.version}")
    print(f"Target: {target}")
    if backup:
        print(f"Backup: {backup}")

def main() -> None:
    parser = argparse.ArgumentParser(prog="shieldnet-plugin")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("source")

    args = parser.parse_args()

    if os.geteuid() != 0:
        fail("Run as root")

    if args.command == "install":
        source = Path(args.source).resolve()
        if not source.is_dir() or not (source / "plugin.json").is_file():
            fail("Plugin directory or plugin.json not found")
        asyncio.run(install_plugin(source))


if __name__ == "__main__":
    main()
