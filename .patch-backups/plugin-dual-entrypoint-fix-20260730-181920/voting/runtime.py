from __future__ import annotations

import logging

from fastapi import APIRouter

from app.plugins.base import BackendPlugin

logger = logging.getLogger(__name__)


class VotingPlugin(BackendPlugin):
    """Runtime wrapper for the ShieldNet multilingual Voting module."""

    def router(self) -> APIRouter | None:
        # Voting CRUD and internal Discord routes are registered by ShieldNet core.
        return None

    async def startup(self) -> None:
        logger.info(
            "Voting runtime started plugin_key=%s version=%s",
            self.key,
            self.context.manifest.version,
        )

    async def shutdown(self) -> None:
        logger.info(
            "Voting runtime stopped plugin_key=%s",
            self.key,
        )
