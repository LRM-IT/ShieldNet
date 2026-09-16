import asyncio
import json
import logging
import socket
from datetime import UTC, datetime

import httpx
from redis.asyncio import Redis

from scheduler.config import settings

logger = logging.getLogger(__name__)

async def heartbeat(client: httpx.AsyncClient, worker_name: str) -> None:
    response = await client.post(
        f"{settings.backend_url.rstrip('/')}/api/v1/internal/runtime/heartbeat",
        headers={"X-ShieldNet-Service-Token": settings.internal_service_token},
        json={
            "worker_name": worker_name,
            "worker_type": "scheduler",
            "status": "online",
            "metadata": {"queue": settings.worker_queue},
        },
    )
    response.raise_for_status()

async def enqueue(redis: Redis, job: str) -> None:
    payload = {"job": job, "queued_at": datetime.now(UTC).isoformat(), "source": "scheduler"}
    await redis.lpush(settings.worker_queue, json.dumps(payload))
    logger.info("Queued job: %s", job)

async def schedule_tick(client: httpx.AsyncClient, redis: Redis) -> None:
    response = await client.post(f"{settings.backend_url.rstrip('/')}/api/v1/internal/automations/schedules/tick", headers={"X-ShieldNet-Service-Token": settings.internal_service_token})
    response.raise_for_status()
    for automation in response.json().get("jobs", []):
        payload={"job":"automation_execute","guild_id":automation.get("guild_id"),"automation":automation}
        await redis.lpush(settings.worker_queue, json.dumps(payload))
    if response.json().get("count"):
        logger.info("Queued scheduled automations: %s", response.json()["count"])

async def billing_reconcile(client: httpx.AsyncClient) -> None:
    response = await client.post(
        f"{settings.backend_url.rstrip('/')}/api/v1/internal/billing/reconcile",
        headers={"X-ShieldNet-Service-Token": settings.internal_service_token},
    )
    response.raise_for_status()
    if response.json().get("count"):
        logger.info("Disabled expired paid plugins: %s", response.json()["count"])

async def run() -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    worker_name = f"scheduler:{socket.gethostname()}"
    next_run = {"sync_guilds": 0.0, "sync_roles": 0.0, "security_scan": 0.0, "billing_reconcile": 0.0}
    intervals = {
        "sync_guilds": settings.guild_sync_minutes * 60,
        "sync_roles": settings.role_sync_minutes * 60,
        "security_scan": settings.security_scan_minutes * 60,
        "billing_reconcile": 300,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            now = asyncio.get_running_loop().time()
            try:
                await redis.ping()
                await heartbeat(client, worker_name)
                await schedule_tick(client, redis)
                if now >= next_run["billing_reconcile"]:
                    await billing_reconcile(client)
                    next_run["billing_reconcile"] = now + intervals["billing_reconcile"]
                for job, interval in intervals.items():
                    if job == "billing_reconcile":
                        continue
                    if now >= next_run[job]:
                        await enqueue(redis, job)
                        next_run[job] = now + interval
            except Exception:
                logger.exception("Scheduler cycle failed")
            await asyncio.sleep(30)

if __name__ == "__main__":
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
