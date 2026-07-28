import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugins import (
    GuildPluginInstallation,
    PluginEvent,
    PluginInstalledVersion,
    PluginRegistry,
    PluginRuntimeInstance,
    PluginRuntimeState,
)
from app.plugins.manifest import PluginManifest, PluginManifestError
from app.schemas.plugins import PluginManifestResponse, PluginScanResponse

PLUGIN_ROOT = Path("/opt/shieldnet/plugins")


def _checksum(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class PluginService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_plugins(self) -> list[PluginManifestResponse]:
        result = await self.session.execute(select(PluginRegistry).order_by(PluginRegistry.name))
        return [self._response(item) for item in result.scalars().all()]

    async def scan(self) -> PluginScanResponse:
        PLUGIN_ROOT.mkdir(parents=True, exist_ok=True)
        result = await self.session.execute(select(PluginRegistry))
        existing = {item.plugin_key: item for item in result.scalars().all()}
        seen: set[str] = set()
        discovered = 0
        updated = 0
        errors: list[str] = []

        for path in sorted(PLUGIN_ROOT.glob("*/plugin.json")):
            try:
                raw = path.read_bytes()
                parsed = PluginManifest.from_path(path)
                manifest = parsed.raw
                key = parsed.plugin_key
                seen.add(key)
                item = existing.get(key)
                if item is None:
                    item = PluginRegistry(
                        plugin_key=key,
                        name=parsed.name,
                        version=parsed.version,
                        manifest_path=str(path),
                    )
                    self.session.add(item)
                    discovered += 1
                else:
                    updated += 1
                item.name = parsed.name
                item.version = parsed.version
                item.description = parsed.description
                item.author = parsed.author
                item.min_core_version = parsed.min_core_version
                item.manifest_path = str(path)
                item.manifest = manifest
                item.checksum = _checksum(raw)
                item.healthy = True
                item.last_error = None
            except Exception as exc:  # malformed third-party manifest must not stop the scan
                errors.append(str(exc))

        missing = 0
        for key, item in existing.items():
            if key in seen:
                continue

            await self.session.execute(
                delete(PluginRuntimeInstance).where(
                    PluginRuntimeInstance.plugin_key == key
                )
            )
            await self.session.execute(
                delete(GuildPluginInstallation).where(
                    GuildPluginInstallation.plugin_key == key
                )
            )
            await self.session.execute(
                delete(PluginRuntimeState).where(
                    PluginRuntimeState.plugin_key == key
                )
            )
            await self.session.execute(
                delete(PluginInstalledVersion).where(
                    PluginInstalledVersion.plugin_key == key
                )
            )
            await self.session.delete(item)
            missing += 1

        self.session.add(
            PluginEvent(
                plugin_key="core",
                event_type="registry.scan",
                status="success" if not errors else "warning",
                message=f"Discovered {discovered}, updated {updated}, missing {missing}",
                metadata_json={"errors": errors},
            )
        )
        await self.session.commit()
        return PluginScanResponse(discovered=discovered, updated=updated, missing=missing, errors=errors)

    async def set_enabled(self, plugin_key: str, enabled: bool) -> PluginManifestResponse:
        result = await self.session.execute(
            select(PluginRegistry).where(PluginRegistry.plugin_key == plugin_key)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise LookupError("Plugin not found")
        if enabled and not item.healthy:
            raise ValueError("Plugin cannot be enabled while unhealthy")
        item.enabled = enabled
        self.session.add(
            PluginEvent(
                plugin_key=plugin_key,
                event_type="plugin.enabled" if enabled else "plugin.disabled",
                message=f"Plugin {'enabled' if enabled else 'disabled'}",
            )
        )
        await self.session.commit()
        await self.session.refresh(item)
        return self._response(item)

    @staticmethod
    def _response(item: PluginRegistry) -> PluginManifestResponse:
        manifest = item.manifest or {}
        components = manifest.get("components") or {
            "backend": bool(manifest.get("backend")),
            "frontend": bool(manifest.get("frontend")),
            "bot": bool(manifest.get("bot")),
        }
        capabilities = manifest.get("capabilities") or []
        return PluginManifestResponse(
            plugin_key=item.plugin_key,
            name=item.name,
            version=item.version,
            description=item.description,
            author=item.author,
            min_core_version=item.min_core_version,
            manifest_path=item.manifest_path,
            signature_status=item.signature_status,
            enabled=item.enabled,
            healthy=item.healthy,
            last_error=item.last_error,
            capabilities=[str(value) for value in capabilities],
            components={str(key): bool(value) for key, value in components.items()},
            manifest=manifest,
            updated_at=item.updated_at,
        )
