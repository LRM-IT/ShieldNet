from __future__ import annotations

from typing import Any
from fastapi import APIRouter
from app.plugins.base import BackendPlugin

_running = False


class TranslatorGroupsPlugin(BackendPlugin):
    def router(self) -> APIRouter | None:
        return None

    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None


async def setup(context: Any) -> None:
    return None


async def start(context: Any) -> None:
    global _running
    _running = True


async def stop(context: Any) -> None:
    global _running
    _running = False


async def health(context: Any) -> dict[str, Any]:
    return {"status": "ready" if _running else "stopped", "plugin_key": "translator_groups"}
