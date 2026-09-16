from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter
from app.plugins.base import BackendPlugin
logger=logging.getLogger(__name__);_running=False
class AuditSecurityPlugin(BackendPlugin):
 def router(self)->APIRouter|None:return None
 async def startup(self):logger.info("Audit & Security started plugin_key=%s",self.key)
 async def shutdown(self):logger.info("Audit & Security stopped plugin_key=%s",self.key)
async def setup(context:Any):logger.info("Audit & Security setup guild_id=%s",getattr(context,"guild_id",None))
async def start(context:Any):
 global _running;_running=True
async def stop(context:Any):
 global _running;_running=False
async def health(context:Any):return{"status":"ready"if _running else"stopped","plugin_key":"audit_security"}
