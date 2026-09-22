from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


class PlatformDoctorService:
    ENV_FILES = (
        ("backend", Path("/etc/shieldnet/backend/backend.env")),
        ("bot", Path("/etc/shieldnet/bot/bot.env")),
        ("scheduler", Path("/etc/shieldnet/scheduler/scheduler.env")),
    )
    REQUIRED_SCHEMAS = (
        "public", "core", "discord", "verification", "audit", "security", "system"
    )
    REQUIRED_TABLES = (
        "discord.guilds",
        "discord.members",
        "verification.settings",
        "audit.audit_events",
        "security.snapshots",
        "security.findings",
        "system.runtime_heartbeats",
        "system.notifications",
        "system.job_runs",
    )

    @staticmethod
    def _check(name: str, category: str, status: str, message: str, *, details: dict[str, Any] | None = None,
               remediation: str | None = None) -> dict[str, Any]:
        return {
            "name": name,
            "category": category,
            "status": status,
            "message": message,
            "details": details or {},
            "remediation": remediation,
        }

    async def run(self, session: AsyncSession) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        checks.extend(self._environment_checks())
        checks.extend(await self._database_checks(session))
        checks.extend(await self._runtime_checks(session))
        checks.append(await self._redis_check())
        checks.extend(self._configuration_checks())
        checks.extend(self._external_checks())

        summary = {"ok": 0, "warning": 0, "failed": 0, "manual": 0}
        for item in checks:
            summary[item["status"]] = summary.get(item["status"], 0) + 1
        overall = "healthy"
        if summary["failed"]:
            overall = "critical"
        elif summary["warning"]:
            overall = "degraded"

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "overall_status": overall,
            "summary": summary,
            "checks": checks,
        }

    def _environment_checks(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for service, path in self.ENV_FILES:
            if not path.exists():
                result.append(self._check(
                    f"{service} environment", "filesystem", "failed",
                    f"Missing {path}", remediation=f"Create {path} from the deployment template."
                ))
                continue
            readable = os.access(path, os.R_OK)
            stat = path.stat()
            mode = oct(stat.st_mode & 0o777)
            result.append(self._check(
                f"{service} environment", "filesystem", "ok" if readable else "failed",
                "Environment file is readable by backend diagnostics." if readable else "Environment file is not readable.",
                details={"path": str(path), "mode": mode, "uid": stat.st_uid, "gid": stat.st_gid},
                remediation=None if readable else "Use the shared shieldnet-services group and mode 0640."
            ))
        return result

    async def _database_checks(self, session: AsyncSession) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        started = perf_counter()
        row = (await session.execute(text(
            "SELECT current_user, current_database(), current_setting('TimeZone')"
        ))).one()
        latency = round((perf_counter() - started) * 1000, 2)
        db_user, db_name, timezone = row
        result.append(self._check(
            "PostgreSQL connection", "database", "ok", "Database connection succeeded.",
            details={"user": db_user, "database": db_name, "timezone": timezone, "latency_ms": latency}
        ))

        schemas = set((await session.execute(text(
            "SELECT schema_name FROM information_schema.schemata"
        ))).scalars().all())
        for schema in self.REQUIRED_SCHEMAS:
            exists = schema in schemas
            usage = False
            create = False
            if exists:
                usage, create = (await session.execute(text(
                    "SELECT has_schema_privilege(current_user, :schema, 'USAGE'), "
                    "has_schema_privilege(current_user, :schema, 'CREATE')"
                ), {"schema": schema})).one()
            status = "ok" if exists and usage else "failed"
            result.append(self._check(
                f"Schema {schema}", "database", status,
                "Schema exists and USAGE is granted." if status == "ok" else "Schema is missing or USAGE is not granted.",
                details={"exists": exists, "usage": bool(usage), "create": bool(create)},
                remediation=None if status == "ok" else f"GRANT USAGE ON SCHEMA {schema} TO {db_user};"
            ))

        for qualified in self.REQUIRED_TABLES:
            schema, table = qualified.split(".", 1)
            exists = bool(await session.scalar(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema=:schema AND table_name=:table)"
            ), {"schema": schema, "table": table}))
            privileges: dict[str, bool] = {}
            if exists:
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    privileges[privilege.lower()] = bool(await session.scalar(text(
                        "SELECT has_table_privilege(current_user, :table, :privilege)"
                    ), {"table": qualified, "privilege": privilege}))
            required_write = qualified in {"security.snapshots", "security.findings", "system.runtime_heartbeats", "system.notifications", "system.job_runs"}
            permitted = exists and privileges.get("select", False)
            if required_write:
                permitted = permitted and privileges.get("insert", False) and privileges.get("update", False)
            result.append(self._check(
                f"Table {qualified}", "database", "ok" if permitted else "failed",
                "Required table and privileges are available." if permitted else "Required table is missing or privileges are incomplete.",
                details={"exists": exists, "privileges": privileges},
                remediation=None if permitted else f"Grant the ShieldNet backend role required privileges on {qualified}."
            ))

        version = await session.scalar(text("SELECT version_num FROM system.alembic_version LIMIT 1"))
        result.append(self._check(
            "Alembic revision", "database", "ok" if version else "failed",
            f"Current revision: {version}" if version else "Alembic revision is unavailable.",
            details={"revision": version}
        ))
        return result

    async def _runtime_checks(self, session: AsyncSession) -> list[dict[str, Any]]:
        rows = (await session.execute(text(
            "SELECT worker_name, worker_type, status, last_seen_at "
            "FROM system.runtime_heartbeats ORDER BY worker_type, worker_name"
        ))).all()
        cutoff = datetime.now(UTC) - timedelta(seconds=90)
        result: list[dict[str, Any]] = []
        by_type: dict[str, list[tuple[str, str, Any]]] = {}
        for name, worker_type, reported_status, last_seen_at in rows:
            by_type.setdefault(worker_type, []).append((name, reported_status, last_seen_at))
        for worker_type, workers in by_type.items():
            # Container hostnames change on every recreation. Keep live instances;
            # when none is live, show one latest stale instance for the service.
            current = [worker for worker in workers if worker[2] >= cutoff]
            selected = current or [max(workers, key=lambda worker: worker[2])]
            for name, reported_status, last_seen_at in selected:
                online = last_seen_at >= cutoff and reported_status == "online"
                result.append(self._check(
                    f"Runtime {name}", "runtime", "ok" if online else "failed",
                    "Heartbeat is current." if online else "Heartbeat is stale or reports a failure.",
                    details={"worker_type": worker_type, "reported_status": reported_status, "last_seen_at": last_seen_at.isoformat()},
                    remediation=None if online else f"Inspect the current {worker_type} container and its logs."
                ))
        for required in ("discord_worker", "scheduler"):
            if required not in by_type:
                result.append(self._check(
                    f"Runtime {required}", "runtime", "failed", "No heartbeat registered.",
                    remediation=f"Inspect the {required} container and its logs."
                ))
        return result

    async def _redis_check(self) -> dict[str, Any]:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            started = perf_counter()
            await redis.ping()
            latency = round((perf_counter() - started) * 1000, 2)
            queue_depth = int(await redis.llen(settings.discord_job_queue))
            return self._check(
                "Valkey / Redis", "queue", "ok", "Queue backend is reachable.",
                details={"latency_ms": latency, "queue": settings.discord_job_queue, "queue_depth": queue_depth}
            )
        except Exception as exc:
            return self._check(
                "Valkey / Redis", "queue", "failed", f"Queue backend connection failed: {type(exc).__name__}",
                remediation="Check valkey.service and SHIELDNET_REDIS_URL."
            )
        finally:
            await redis.aclose()

    def _configuration_checks(self) -> list[dict[str, Any]]:
        values = (
            ("Discord client ID", bool(settings.discord_client_id), "Set SHIELDNET_DISCORD_CLIENT_ID."),
            ("Discord client secret", bool(settings.discord_client_secret), "Set SHIELDNET_DISCORD_CLIENT_SECRET."),
            ("Discord redirect URI", bool(settings.discord_redirect_uri), "Set SHIELDNET_DISCORD_REDIRECT_URI."),
            ("Internal service token", len(settings.internal_service_token) >= 24, "Use a strong SHIELDNET_INTERNAL_SERVICE_TOKEN."),
            ("Application secret", len(settings.secret_key) >= 32, "Use a SHIELDNET_SECRET_KEY of at least 32 characters."),
            ("SuperAdmin IDs", bool(settings.superadmin_id_set), "Set SHIELDNET_SUPERADMIN_IDS."),
        )
        return [self._check(
            name, "configuration", "ok" if valid else "warning",
            "Configured." if valid else "Configuration is missing or weak.",
            remediation=None if valid else remediation
        ) for name, valid, remediation in values]

    def _external_checks(self) -> list[dict[str, Any]]:
        return [
            self._check("systemd units", "host", "manual", "Run the root CLI doctor to validate unit files and service state."),
            self._check("Nginx and WebSocket proxy", "host", "manual", "Run the root CLI doctor to validate nginx -t and Upgrade headers."),
            self._check("Discord privileged intents", "discord", "manual", "Confirm Server Members Intent and Presence Intent in Discord Developer Portal."),
            self._check("PostgreSQL default privileges", "database", "manual", "Run the root CLI doctor to inspect owner-scoped ALTER DEFAULT PRIVILEGES."),
        ]
