from __future__ import annotations

import logging

from fastapi import APIRouter

from app.plugins.base import BackendPlugin

logger = logging.getLogger(__name__)


class WelcomePlugin(BackendPlugin):
    """Runtime wrapper for the ShieldNet Welcome module."""

    def router(self) -> APIRouter | None:
        # Welcome HTTP routes are currently registered by ShieldNet core.
        return None

    async def startup(self) -> None:
        logger.info(
            "Welcome runtime started plugin_key=%s",
            self.key,
        )

    async def shutdown(self) -> None:
        logger.info(
            "Welcome runtime stopped plugin_key=%s",
            self.key,
        )
