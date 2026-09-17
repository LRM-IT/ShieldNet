from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Awaitable, Callable

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.discord import BotStatus, Guild
from app.models.jobs import SystemJobRun
from app.models.members import DiscordMember

JobHandler = Callable[[AsyncSession], Awaitable[dict[str, Any]]]


class JobService:
    DEFINITIONS = {
        "database_probe": {
            "name": "Database probe",
            "description": "Checks PostgreSQL connectivity and reports the active database and time zone.",
            "category": "health",
        },
        "guild_registry_snapshot": {
            "name": "Guild registry snapshot",
            "description": "Calculates registry totals and identifies guilds that have not synchronized recently.",
            "category": "discord",
        },
        "member_index_snapshot": {
            "name": "Member index snapshot",
            "description": "Validates the member index and reports active and inactive member totals.",
            "category": "members",
        },
        "audit_snapshot": {
            "name": "Audit snapshot",
            "description": "Reports audit volume and the latest recorded platform event.",
            "category": "audit",
        },
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _database_probe(self) -> dict[str, Any]:
        row = (await self.session.execute(text(
            "SELECT current_database() AS database_name, current_user AS database_user, "
            "current_setting('TimeZone') AS timezone, now() AS server_time"
        ))).mappings().one()
        result = dict(row)
        if isinstance(result.get("server_time"), datetime):
            result["server_time"] = result["server_time"].isoformat()
        return result

    async def _guild_registry_snapshot(self) -> dict[str, Any]:
        total = int(await self.session.scalar(select(func.count()).select_from(Guild)) or 0)
        with_bot = int(await self.session.scalar(
            select(func.count()).select_from(Guild).where(Guild.bot_status == BotStatus.ONLINE)
        ) or 0)
        never_synced = int(await self.session.scalar(
            select(func.count()).select_from(Guild).where(Guild.last_sync_at.is_(None))
        ) or 0)
        return {"guilds": total, "bot_online": with_bot, "never_synced": never_synced}

    async def _member_index_snapshot(self) -> dict[str, Any]:
        total = int(await self.session.scalar(select(func.count()).select_from(DiscordMember)) or 0)
        active = int(await self.session.scalar(
            select(func.count()).select_from(DiscordMember).where(DiscordMember.is_active.is_(True))
        ) or 0)
        return {"members": total, "active": active, "inactive": max(total - active, 0)}

    async def _audit_snapshot(self) -> dict[str, Any]:
        total = int(await self.session.scalar(select(func.count()).select_from(AuditEvent)) or 0)
        latest = (await self.session.execute(
            select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        return {
            "events": total,
            "latest_event_type": latest.event_type if latest else None,
            "latest_event_at": latest.created_at.isoformat() if latest else None,
        }

    async def execute(self, job_key: str, requested_by: Any | None) -> SystemJobRun:
        if job_key not in self.DEFINITIONS:
            raise KeyError(job_key)

        run = SystemJobRun(job_key=job_key, status="running", trigger="manual", requested_by=requested_by)
        self.session.add(run)
        await self.session.flush()

        started = datetime.now(UTC)
        run.started_at = started
        timer = perf_counter()
        try:
            handler = getattr(self, f"_{job_key}")
            run.result = await handler()
            run.status = "success"
        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)[:2000]
        finally:
            run.finished_at = datetime.now(UTC)
            run.duration_ms = int((perf_counter() - timer) * 1000)
            await self.session.commit()
            await self.session.refresh(run)
        return run

    async def overview(self) -> dict[str, Any]:
        latest_rows = (await self.session.execute(
            select(SystemJobRun).order_by(SystemJobRun.created_at.desc()).limit(50)
        )).scalars().all()

        latest_by_key: dict[str, SystemJobRun] = {}
        for item in latest_rows:
            latest_by_key.setdefault(item.job_key, item)

        jobs = []
        for key, definition in self.DEFINITIONS.items():
            last = latest_by_key.get(key)
            jobs.append({
                "key": key,
                **definition,
                "safe_manual_run": True,
                "last_status": last.status if last else None,
                "last_run_at": last.finished_at if last else None,
                "last_duration_ms": last.duration_ms if last else None,
            })

        recent = latest_rows[:20]
        failed = sum(1 for item in recent if item.status == "failed")
        running = sum(1 for item in recent if item.status == "running")
        db_started = perf_counter()
        await self.session.execute(text("SELECT 1"))
        db_latency = int((perf_counter() - db_started) * 1000)

        return {
            "generated_at": datetime.now(UTC),
            "totals": {
                "registered_jobs": len(jobs),
                "recent_runs": len(recent),
                "failed_runs": failed,
                "running_runs": running,
            },
            "jobs": jobs,
            "recent_runs": [self.serialize_run(item) for item in recent],
            "health": {
                "backend": "online",
                "database": "online",
                "database_latency_ms": db_latency,
                "scheduler": "manual",
                "worker": "inline-safe-jobs",
            },
        }

    @staticmethod
    def serialize_run(run: SystemJobRun) -> dict[str, Any]:
        return {
            "id": str(run.id),
            "job_key": run.job_key,
            "status": run.status,
            "trigger": run.trigger,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "duration_ms": run.duration_ms,
            "result": run.result or {},
            "error_message": run.error_message,
            "created_at": run.created_at,
        }
