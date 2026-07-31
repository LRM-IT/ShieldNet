from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter
from app.plugins.base import BackendPlugin
logger = logging.getLogger(__name__)
_process_started = False
class VerificationLevel1Plugin(BackendPlugin):
    def router(self) -> APIRouter | None:
        from backend.router import router
        return router
    async def startup(self) -> None:
        logger.info("Verification Level 1 backend started plugin_key=%s", self.key)
    async def shutdown(self) -> None:
        logger.info("Verification Level 1 backend stopped plugin_key=%s", self.key)
async def setup(context: Any) -> None:
    logger.info("Verification Level 1 runtime setup guild_id=%s plugin_key=%s generation=%s", getattr(context,"guild_id",None), getattr(context,"plugin_key",None), getattr(context,"generation",None))
async def start(context: Any) -> None:
    global _process_started
    _process_started=True
    logger.info("Verification Level 1 runtime started guild_id=%s plugin_key=%s", getattr(context,"guild_id",None), getattr(context,"plugin_key",None))
async def stop(context: Any) -> None:
    global _process_started
    _process_started=False
    logger.info("Verification Level 1 runtime stopped guild_id=%s plugin_key=%s", getattr(context,"guild_id",None), getattr(context,"plugin_key",None))
async def health(context: Any) -> dict[str, Any]:
    return {"status":"ready" if _process_started else "stopped","plugin_key":"verification_level1","guild_id":getattr(context,"guild_id",None)}
