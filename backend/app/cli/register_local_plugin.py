from __future__ import annotations

import argparse
import asyncio
import hashlib
from pathlib import Path

from sqlalchemy import select

from app.db.session import AsyncSessionFactory
from app.models.plugins import PluginRegistry
from app.plugins.manifest import PluginManifest
from app.services.plugin_service import PLUGIN_ROOT


async def register(plugin_key: str, *, enable: bool = False) -> None:
    path = (PLUGIN_ROOT / plugin_key / "plugin.json").resolve()
    if path.parent.parent != PLUGIN_ROOT.resolve() or not path.is_file():
        raise SystemExit(f"Local plugin manifest not found: {plugin_key}")
    raw = path.read_bytes()
    parsed = PluginManifest.from_path(path)
    if parsed.plugin_key != plugin_key:
        raise SystemExit("Manifest ID does not match requested plugin key")
    async with AsyncSessionFactory() as session:
        item = await session.scalar(
            select(PluginRegistry).where(PluginRegistry.plugin_key == plugin_key)
        )
        created = item is None
        if item is None:
            item = PluginRegistry(
                plugin_key=plugin_key,
                name=parsed.name,
                version=parsed.version,
                manifest_path=str(path),
            )
            session.add(item)
        item.name = parsed.name
        item.version = parsed.version
        item.description = parsed.description
        item.author = parsed.author
        item.min_core_version = parsed.min_core_version
        item.manifest_path = str(path)
        item.manifest = parsed.raw
        item.checksum = hashlib.sha256(raw).hexdigest()
        item.healthy = True
        item.last_error = None
        if enable:
            item.enabled = True
        await session.commit()
    state = " enabled" if enable else ""
    print(f"{'registered' if created else 'updated'} {plugin_key} {parsed.version}{state}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Register one local plugin without scanning or deleting others.")
    parser.add_argument("plugin_key")
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Enable the registered plugin after its manifest has been validated.",
    )
    args = parser.parse_args()
    asyncio.run(register(args.plugin_key.strip().lower(), enable=args.enable))


if __name__ == "__main__":
    main()
