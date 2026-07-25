import asyncio
import os
import shutil
from datetime import UTC, datetime, timedelta
from time import perf_counter

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import AsyncSessionFactory, get_db_session
from app.models.audit import AuditEvent
from app.models.core import GlobalRole, User, UserStatus
from app.models.runtime import RuntimeHeartbeat
from app.services.global_access import GlobalAccessService

router = APIRouter(prefix="/platform/operations", tags=["Platform Operations"])


def _read_memory() -> tuple[int, int]:
    values: dict[str, int] = {}
    try:
        for line in open("/proc/meminfo", encoding="utf-8"):
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0]) * 1024
    except (OSError, ValueError):
        return 0, 0
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    return total, max(0, total - available)


def _system_metrics() -> dict:
    memory_total, memory_used = _read_memory()
    disk = shutil.disk_usage("/")
    try:
        load_1m, load_5m, load_15m = os.getloadavg()
    except OSError:
        load_1m = load_5m = load_15m = 0.0
    cpu_count = os.cpu_count() or 1
    return {
        "status": "online",
        "cpu_count": cpu_count,
        "load_1m": round(load_1m, 2),
        "load_5m": round(load_5m, 2),
        "load_15m": round(load_15m, 2),
        "load_percent": round(min(100.0, load_1m / cpu_count * 100), 1),
        "memory_total_bytes": memory_total,
        "memory_used_bytes": memory_used,
        "memory_percent": round(memory_used / memory_total * 100, 1) if memory_total else 0.0,
        "disk_total_bytes": disk.total,
        "disk_used_bytes": disk.used,
        "disk_percent": round(disk.used / disk.total * 100, 1) if disk.total else 0.0,
    }


def _require(user: User) -> None:
    GlobalAccessService.require_any(user, (GlobalRole.SUPERADMIN, GlobalRole.ADMIN))


async def _snapshot(session: AsyncSession) -> dict:
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=90)
    db_started = perf_counter()
    await session.execute(text("SELECT 1"))
    db_latency = round((perf_counter() - db_started) * 1000, 2)

    workers = list((await session.scalars(
        select(RuntimeHeartbeat).order_by(RuntimeHeartbeat.worker_type, RuntimeHeartbeat.worker_name)
    )).all())
    events = list((await session.scalars(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(30)
    )).all())

    redis_status = "offline"
    redis_latency = None
    queue_depth = 0
    redis_memory = None
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        started = perf_counter()
        await redis.ping()
        redis_latency = round((perf_counter() - started) * 1000, 2)
        queue_depth = int(await redis.llen(settings.discord_job_queue))
        info = await redis.info("memory")
        redis_memory = int(info.get("used_memory", 0))
        redis_status = "online"
    except Exception:
        pass
    finally:
        await redis.aclose()

    return {
        "generated_at": now.isoformat(),
        "components": {
            "backend": {"status": "online"},
            "system": _system_metrics(),
            "postgresql": {"status": "online", "latency_ms": db_latency},
            "valkey": {
                "status": redis_status,
                "latency_ms": redis_latency,
                "queue_depth": queue_depth,
                "memory_bytes": redis_memory,
            },
        },
        "workers": [
            {
                "worker_name": item.worker_name,
                "worker_type": item.worker_type,
                "status": "online" if item.last_seen_at >= cutoff else "stale",
                "reported_status": item.status,
                "metadata": item.metadata_json,
                "started_at": item.started_at.isoformat(),
                "last_seen_at": item.last_seen_at.isoformat(),
            }
            for item in workers
        ],
        "events": [
            {
                "id": str(event.id),
                "guild_id": str(event.guild_id) if event.guild_id is not None else None,
                "event_type": event.event_type,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "result": event.result,
                "message": event.message,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
    }


@router.get("/snapshot")
async def operations_snapshot(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require(current_user)
    return await _snapshot(session)


async def _authenticate_websocket(token: str) -> User | None:
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        async with AsyncSessionFactory() as session:
            user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if user is None or user.status != UserStatus.ACTIVE:
                return None
            _require(user)
            return user
    except Exception:
        return None


@router.websocket("/ws")
async def operations_websocket(websocket: WebSocket, token: str = Query(default="")) -> None:
    user = await _authenticate_websocket(token)
    if user is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            async with AsyncSessionFactory() as session:
                await websocket.send_json(await _snapshot(session))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
