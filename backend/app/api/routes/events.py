from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.events import Event, event_bus
from app.core.security import decode_access_token
from app.db.session import AsyncSessionFactory
from app.models.core import User, UserStatus

router = APIRouter(tags=["Runtime"])


def _serialize_event(event: Event) -> dict[str, Any]:
    return {
        "type": event.name,
        "payload": dict(event.payload),
        "guild_id": str(event.guild_id) if event.guild_id is not None else None,
        "actor_id": str(event.actor_id) if event.actor_id is not None else None,
        "source": event.source,
        "correlation_id": str(event.correlation_id),
        "created_at": event.created_at.isoformat(),
    }


def _extract_token(websocket: WebSocket) -> str | None:
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    offered = [item.strip() for item in protocols.split(",") if item.strip()]
    if len(offered) >= 2 and offered[0] == "shieldnet":
        return offered[1]
    return websocket.query_params.get("access_token")


async def _authenticate_websocket(websocket: WebSocket) -> User | None:
    token = _extract_token(websocket)
    if not token:
        return None

    try:
        payload = decode_access_token(token)
    except Exception:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or user.status != UserStatus.ACTIVE:
            return None
        return user


@router.get("/runtime/events")
async def event_bus_status() -> dict[str, object]:
    snapshot = await event_bus.snapshot()
    return {
        "status": "ok" if snapshot.started else "stopped",
        "started": snapshot.started,
        "subscribers": snapshot.subscribers,
        "event_names": snapshot.event_names,
        "published": snapshot.published,
        "delivered": snapshot.delivered,
        "failed": snapshot.failed,
        "active_dispatches": snapshot.active_dispatches,
        "average_dispatch_ms": snapshot.average_dispatch_ms,
    }


@router.websocket("/events/ws")
async def event_stream(websocket: WebSocket) -> None:
    user = await _authenticate_websocket(websocket)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return

    await websocket.accept(subprotocol="shieldnet")
    queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=250)

    async def forward(event: Event) -> None:
        if queue.full():
            with suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        with suppress(asyncio.QueueFull):
            queue.put_nowait(event)

    await event_bus.subscribe("*", forward)
    await websocket.send_json({
        "type": "system.connected",
        "payload": {"user_id": str(user.id)},
        "source": "event-stream",
    })

    async def sender() -> None:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25)
                await websocket.send_json(_serialize_event(event))
            except TimeoutError:
                await websocket.send_json({
                    "type": "system.ping",
                    "payload": {},
                    "source": "event-stream",
                })

    send_task = asyncio.create_task(sender())
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({
                    "type": "system.pong",
                    "payload": {},
                    "source": "event-stream",
                })
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        with suppress(asyncio.CancelledError):
            await send_task
        await event_bus.unsubscribe("*", forward)
