import base64
import os
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugin_control import (
    PluginActivationHistory, PluginActivationState, PluginPackageHistory,
    PluginPermission, PluginPermissionAudit, PluginPermissionGrant,
    PluginSecret, PluginSecretAudit,
)

DEFAULT_PERMISSIONS = {
    "settings.read": ("Read plugin settings", "low"),
    "settings.write": ("Modify plugin settings", "medium"),
    "events.publish": ("Publish platform events", "medium"),
    "notifications.send": ("Send notifications", "medium"),
    "secrets.read": ("Read encrypted plugin secrets", "high"),
    "runtime.control": ("Start and stop plugin runtime", "high"),
}


def _vault_key() -> bytes:
    raw = os.getenv("SHIELDNET_PLUGIN_VAULT_KEY", "")
    if not raw:
        raise RuntimeError("SHIELDNET_PLUGIN_VAULT_KEY is not configured")
    try:
        key = base64.urlsafe_b64decode(raw.encode())
    except Exception as exc:
        raise RuntimeError("SHIELDNET_PLUGIN_VAULT_KEY must be urlsafe base64") from exc
    if len(key) != 32:
        raise RuntimeError("SHIELDNET_PLUGIN_VAULT_KEY must decode to 32 bytes")
    return key


class PluginControlService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_permissions(self) -> None:
        result = await self.session.execute(select(PluginPermission.permission_key))
        existing = set(result.scalars().all())
        for key, (description, risk) in DEFAULT_PERMISSIONS.items():
            if key not in existing:
                self.session.add(PluginPermission(permission_key=key, description=description, risk_level=risk))
        await self.session.flush()

    async def permissions(self, plugin_key: str):
        await self.ensure_permissions()
        catalog = (await self.session.execute(select(PluginPermission).order_by(PluginPermission.permission_key))).scalars().all()
        grants = (await self.session.execute(select(PluginPermissionGrant).where(PluginPermissionGrant.plugin_key == plugin_key))).scalars().all()
        granted = {x.permission_key: x.granted for x in grants}
        await self.session.commit()
        return [{"permission_key": x.permission_key, "description": x.description, "risk_level": x.risk_level, "granted": granted.get(x.permission_key, False)} for x in catalog]

    async def update_permissions(self, plugin_key: str, values: dict[str, bool], actor_id: uuid.UUID | None):
        await self.ensure_permissions()
        valid = set((await self.session.execute(select(PluginPermission.permission_key))).scalars().all())
        unknown = sorted(set(values) - valid)
        if unknown:
            raise ValueError(f"Unknown permissions: {', '.join(unknown)}")
        for permission_key, granted in values.items():
            row = (await self.session.execute(select(PluginPermissionGrant).where(PluginPermissionGrant.plugin_key == plugin_key, PluginPermissionGrant.permission_key == permission_key))).scalar_one_or_none()
            old = bool(row.granted) if row else False
            if row is None:
                row = PluginPermissionGrant(plugin_key=plugin_key, permission_key=permission_key)
                self.session.add(row)
            row.granted = granted
            row.granted_by_user_id = actor_id
            self.session.add(PluginPermissionAudit(plugin_key=plugin_key, permission_key=permission_key, action="grant" if granted else "revoke", actor_user_id=actor_id, metadata_json={"previous": old, "current": granted}))
        await self.session.commit()
        return await self.permissions(plugin_key)

    async def list_secrets(self, plugin_key: str):
        return (await self.session.execute(select(PluginSecret).where(PluginSecret.plugin_key == plugin_key).order_by(PluginSecret.secret_name))).scalars().all()

    async def get_secret(self, plugin_key: str, name: str, scope: str = "platform", scope_key: str = "global") -> str | None:
        row = (await self.session.execute(select(PluginSecret).where(
            PluginSecret.plugin_key == plugin_key,
            PluginSecret.scope == scope,
            PluginSecret.scope_key == scope_key,
            PluginSecret.secret_name == name,
        ))).scalar_one_or_none()
        if row is None:
            return None
        return AESGCM(_vault_key()).decrypt(
            row.nonce,
            row.ciphertext,
            f"{plugin_key}:{scope}:{scope_key}:{name}".encode(),
        ).decode()

    async def put_secret(self, plugin_key: str, name: str, value: str, scope: str, scope_key: str, actor_id: uuid.UUID | None):
        nonce = os.urandom(12)
        ciphertext = AESGCM(_vault_key()).encrypt(nonce, value.encode(), f"{plugin_key}:{scope}:{scope_key}:{name}".encode())
        row = (await self.session.execute(select(PluginSecret).where(PluginSecret.plugin_key == plugin_key, PluginSecret.scope == scope, PluginSecret.scope_key == scope_key, PluginSecret.secret_name == name))).scalar_one_or_none()
        action = "update" if row else "create"
        if row is None:
            row = PluginSecret(plugin_key=plugin_key, scope=scope, scope_key=scope_key, secret_name=name, ciphertext=ciphertext, nonce=nonce, created_by_user_id=actor_id)
            self.session.add(row)
        else:
            row.ciphertext, row.nonce, row.key_version = ciphertext, nonce, row.key_version + 1
        self.session.add(PluginSecretAudit(plugin_key=plugin_key, secret_name=name, action=action, actor_user_id=actor_id))
        await self.session.commit(); await self.session.refresh(row)
        return row

    async def delete_secret(self, plugin_key: str, name: str, scope: str, scope_key: str, actor_id: uuid.UUID | None):
        row = (await self.session.execute(select(PluginSecret).where(PluginSecret.plugin_key == plugin_key, PluginSecret.scope == scope, PluginSecret.scope_key == scope_key, PluginSecret.secret_name == name))).scalar_one_or_none()
        if row is None: raise LookupError("Secret not found")
        await self.session.delete(row)
        self.session.add(PluginSecretAudit(plugin_key=plugin_key, secret_name=name, action="delete", actor_user_id=actor_id))
        await self.session.commit()

    async def activation(self, plugin_key: str):
        row = (await self.session.execute(select(PluginActivationState).where(PluginActivationState.plugin_key == plugin_key))).scalar_one_or_none()
        if row is None:
            row = PluginActivationState(plugin_key=plugin_key)
            self.session.add(row); await self.session.commit(); await self.session.refresh(row)
        return row

    async def transition(self, plugin_key: str, action: str, actor_id: uuid.UUID | None):
        row = await self.activation(plugin_key); previous = row.state
        transitions = {"start": "running", "stop": "stopped", "restart": "running", "enable": row.state, "disable": "stopped"}
        if action not in transitions: raise ValueError("Unsupported action")
        if action == "start" and row.maintenance: raise ValueError("Plugin is in maintenance mode")
        row.state = transitions[action]
        if action == "enable": row.enabled = True
        elif action == "disable": row.enabled = False
        elif action == "restart": row.restart_count += 1
        row.last_error = None
        self.session.add(PluginActivationHistory(plugin_key=plugin_key, action=action, previous_state=previous, new_state=row.state, actor_user_id=actor_id))
        await self.session.commit(); await self.session.refresh(row)
        return row

    async def maintenance(self, plugin_key: str, enabled: bool, actor_id: uuid.UUID | None):
        row = await self.activation(plugin_key); previous = row.state
        row.maintenance = enabled
        self.session.add(PluginActivationHistory(plugin_key=plugin_key, action="maintenance_on" if enabled else "maintenance_off", previous_state=previous, new_state=row.state, actor_user_id=actor_id))
        await self.session.commit(); await self.session.refresh(row)
        return row

    async def versions(self, plugin_key: str):
        return (await self.session.execute(select(PluginPackageHistory).where(PluginPackageHistory.plugin_key == plugin_key).order_by(PluginPackageHistory.created_at.desc()))).scalars().all()
