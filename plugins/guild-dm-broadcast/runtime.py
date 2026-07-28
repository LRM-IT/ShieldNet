from __future__ import annotations

from typing import Any


async def setup(context: Any) -> None:
    """Validate that the ShieldNet runtime context is available."""
    if not getattr(context, "plugin_key", None):
        raise RuntimeError("ShieldNet plugin context has no plugin_key")
    if not getattr(context, "guild_id", None):
        raise RuntimeError("ShieldNet plugin context has no guild_id")


async def start(context: Any) -> None:
    """
    Guild DM delivery is performed by the main ShieldNet bot worker.

    This runtime process represents the enabled per-guild plugin lifecycle
    and remains alive under the ShieldNet runtime manager.
    """
    return None


async def stop(context: Any) -> None:
    """No plugin-owned background resources require cleanup."""
    return None
