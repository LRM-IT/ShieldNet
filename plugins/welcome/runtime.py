from __future__ import annotations

from typing import Any

_context: Any | None = None
_started = False


async def on_load(context: Any) -> None:
    global _context
    _context = context
    context.logger.info("Welcome plugin loaded")


async def on_start(context: Any) -> None:
    global _context, _started
    _context = context
    _started = True
    context.logger.info("Welcome plugin started")


async def on_stop(context: Any) -> None:
    global _started
    _started = False
    context.logger.info("Welcome plugin stopped")


async def on_unload(context: Any) -> None:
    global _context
    _context = None
    context.logger.info("Welcome plugin unloaded")


async def health(context: Any) -> dict[str, Any]:
    return {
        "status": "ready" if _started else "stopped",
        "plugin_key": "welcome",
        "version": "1.0.3",
    }
