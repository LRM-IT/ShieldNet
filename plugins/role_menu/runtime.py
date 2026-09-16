from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter
from app.plugins.base import BackendPlugin

logger = logging.getLogger(__name__)
_running = False

class RoleMenuPlugin(BackendPlugin):
    def router(self) -> APIRouter | None: return None
    async def startup(self) -> None: logger.info("Role Menu backend started plugin_key=%s", self.key)
    async def shutdown(self) -> None: logger.info("Role Menu backend stopped plugin_key=%s", self.key)

async def setup(context: Any) -> None: logger.info("Role Menu setup guild_id=%s", getattr(context, "guild_id", None))
async def start(context: Any) -> None:
    global _running; _running = True
async def stop(context: Any) -> None:
    global _running; _running = False
async def health(context: Any) -> dict[str, Any]: return {"status": "ready" if _running else "stopped", "plugin_key": "role_menu"}
