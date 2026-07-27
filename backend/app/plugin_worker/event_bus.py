from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4


EventHandler = Callable[["RuntimeEvent"], Awaitable[None] | None]


class RuntimeEventBusError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    name: str
    source: str
    payload: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class EventDeliveryResult:
    event: RuntimeEvent
    delivered: int
    failed: int
    errors: tuple[str, ...]


class RuntimeEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        event_name: str,
        handler: EventHandler,
    ) -> None:
        name = self._normalize_name(event_name)
        if not callable(handler):
            raise RuntimeEventBusError("Event handler must be callable")

        async with self._lock:
            handlers = (
                self._wildcard_handlers
                if name == "*"
                else self._handlers[name]
            )
            if handler not in handlers:
                handlers.append(handler)

    async def unsubscribe(
        self,
        event_name: str,
        handler: EventHandler,
    ) -> None:
        name = self._normalize_name(event_name)
        async with self._lock:
            handlers = (
                self._wildcard_handlers
                if name == "*"
                else self._handlers.get(name, [])
            )
            if handler in handlers:
                handlers.remove(handler)

    async def publish(
        self,
        event_name: str,
        *,
        source: str,
        payload: dict[str, Any] | None = None,
    ) -> EventDeliveryResult:
        name = self._normalize_name(event_name)
        event = RuntimeEvent(
            event_id=str(uuid4()),
            name=name,
            source=source.strip() or "shieldnet",
            payload=dict(payload or {}),
            created_at=datetime.now(timezone.utc),
        )

        async with self._lock:
            handlers = tuple(
                self._handlers.get(name, ())
            ) + tuple(self._wildcard_handlers)

        delivered = 0
        errors: list[str] = []
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
                delivered += 1
            except Exception as exc:
                errors.append(str(exc))

        return EventDeliveryResult(
            event=event,
            delivered=delivered,
            failed=len(errors),
            errors=tuple(errors),
        )

    @staticmethod
    def _normalize_name(event_name: str) -> str:
        name = event_name.strip().lower()
        if not name:
            raise RuntimeEventBusError(
                "Event name must not be empty"
            )
        return name
