from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.db.session import get_db_session
from app.models.audit import AuditEvent
from app.models.core import User
from app.models.discord import Guild, GuildMembership, MembershipStatus
from app.models.jobs import SystemJobRun
from app.models.member_cases import MemberCase
from app.models.members import DiscordMember
from app.models.notifications import PlatformNotification
from app.models.plugins import GuildPluginInstallation
from app.models.runtime import RuntimeHeartbeat
from app.models.security import SecurityFinding, SecuritySeverity

router = APIRouter(prefix="/platform/dashboard", tags=["Enterprise Dashboard"])


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


async def _accessible_guilds(session: AsyncSession, user: User) -> list[Guild]:
    if getattr(user, "is_superadmin", False):
        query = select(Guild).order_by(Guild.name)
    else:
        query = (
            select(Guild)
            .join(GuildMembership, GuildMembership.guild_id == Guild.guild_id)
            .where(
                GuildMembership.user_id == user.id,
                GuildMembership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Guild.name)
        )
    return list((await session.scalars(query)).unique().all())


@router.get("/overview")
async def enterprise_overview(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    stale_cutoff = now - timedelta(seconds=90)

    db_started = perf_counter()
    await session.execute(text("SELECT 1"))
    db_latency_ms = round((perf_counter() - db_started) * 1000, 2)

    guilds = await _accessible_guilds(session, current_user)
    guild_ids = [item.guild_id for item in guilds]

    members_total = 0
    active_members = 0
    bots_total = 0
    watchlisted = 0
    open_cases = 0
    overdue_cases = 0
    critical_security = 0
    audit_24h = 0
    enabled_plugins_total = 0
    guild_plugin_counts: dict[int, int] = {}

    if guild_ids:
        member_stats = (await session.execute(
            select(
                func.count(DiscordMember.id),
                func.sum(case((DiscordMember.is_active.is_(True), 1), else_=0)),
                func.sum(case((DiscordMember.bot.is_(True), 1), else_=0)),
                func.sum(case((DiscordMember.watchlisted.is_(True), 1), else_=0)),
            ).where(DiscordMember.guild_id.in_(guild_ids))
        )).one()
        members_total = int(member_stats[0] or 0)
        active_members = int(member_stats[1] or 0)
        bots_total = int(member_stats[2] or 0)
        watchlisted = int(member_stats[3] or 0)

        open_cases = int(await session.scalar(
            select(func.count(MemberCase.id)).where(
                MemberCase.guild_id.in_(guild_ids),
                MemberCase.status.in_(("open", "investigating")),
            )
        ) or 0)
        overdue_cases = int(await session.scalar(
            select(func.count(MemberCase.id)).where(
                MemberCase.guild_id.in_(guild_ids),
                MemberCase.status.in_(("open", "investigating")),
                MemberCase.due_at.is_not(None),
                MemberCase.due_at < now,
            )
        ) or 0)
        critical_security = int(await session.scalar(
            select(func.count(SecurityFinding.id)).where(
                SecurityFinding.guild_id.in_(guild_ids),
                SecurityFinding.status == "open",
                SecurityFinding.severity.in_((SecuritySeverity.HIGH, SecuritySeverity.CRITICAL)),
            )
        ) or 0)
        audit_24h = int(await session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.guild_id.in_(guild_ids),
                AuditEvent.created_at >= day_ago,
            )
        ) or 0)

        plugin_rows = (await session.execute(
            select(
                GuildPluginInstallation.guild_id,
                func.count(GuildPluginInstallation.id),
            ).where(
                GuildPluginInstallation.guild_id.in_(guild_ids),
                GuildPluginInstallation.enabled.is_(True),
            ).group_by(GuildPluginInstallation.guild_id)
        )).all()
        guild_plugin_counts = {int(guild_id): int(count or 0) for guild_id, count in plugin_rows}
        enabled_plugins_total = sum(guild_plugin_counts.values())

    workers = list((await session.scalars(
        select(RuntimeHeartbeat).order_by(RuntimeHeartbeat.worker_type, RuntimeHeartbeat.worker_name)
    )).all())
    worker_items = [
        {
            "name": item.worker_name,
            "type": item.worker_type,
            "status": "online" if item.last_seen_at >= stale_cutoff else "stale",
            "reported_status": item.status,
            "last_seen_at": item.last_seen_at.isoformat(),
            "metadata": item.metadata_json,
        }
        for item in workers
    ]

    open_alerts = int(await session.scalar(
        select(func.count(PlatformNotification.id)).where(PlatformNotification.status == "open")
    ) or 0)
    critical_alerts = int(await session.scalar(
        select(func.count(PlatformNotification.id)).where(
            PlatformNotification.status == "open",
            PlatformNotification.severity == "critical",
        )
    ) or 0)
    failed_jobs_24h = int(await session.scalar(
        select(func.count(SystemJobRun.id)).where(
            SystemJobRun.created_at >= day_ago,
            SystemJobRun.status == "failed",
        )
    ) or 0)
    successful_jobs_7d = int(await session.scalar(
        select(func.count(SystemJobRun.id)).where(
            SystemJobRun.created_at >= week_ago,
            SystemJobRun.status.in_(("success", "completed")),
        )
    ) or 0)

    redis_status = "offline"
    redis_latency_ms = None
    queue_depth = 0
    redis_memory_bytes = None
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        started = perf_counter()
        await redis.ping()
        redis_latency_ms = round((perf_counter() - started) * 1000, 2)
        queue_depth = int(await redis.llen(settings.discord_job_queue))
        memory = await redis.info("memory")
        redis_memory_bytes = int(memory.get("used_memory", 0))
        redis_status = "online"
    except Exception:
        pass
    finally:
        await redis.aclose()

    guild_cards = []
    for guild in guilds[:12]:
        guild_cards.append({
            "guild_id": str(guild.guild_id),
            "name": guild.name,
            "icon_url": guild.icon_url,
            "member_count": guild.member_count,
            "status": _enum_value(guild.status),
            "bot_status": _enum_value(guild.bot_status),
            "last_sync_at": guild.last_sync_at.isoformat() if guild.last_sync_at else None,
            "sync_status": (
                "never" if guild.last_sync_at is None
                else "stale" if guild.last_sync_at < now - timedelta(minutes=15)
                else "fresh"
            ),
            "enabled_plugins": guild_plugin_counts.get(int(guild.guild_id), 0),
        })

    health_values = ["online", "online", redis_status]
    health_values.extend(item["status"] for item in worker_items)
    overall_status = "healthy"
    if "stale" in health_values or redis_status == "offline":
        overall_status = "degraded"
    if critical_alerts > 0:
        overall_status = "critical"

    return {
        "generated_at": now.isoformat(),
        "overall_status": overall_status,
        "scope": "global" if getattr(current_user, "is_superadmin", False) else "assigned",
        "components": {
            "backend": {"status": "online"},
            "postgresql": {"status": "online", "latency_ms": db_latency_ms},
            "valkey": {
                "status": redis_status,
                "latency_ms": redis_latency_ms,
                "memory_bytes": redis_memory_bytes,
                "queue_depth": queue_depth,
            },
        },
        "metrics": {
            "guilds": len(guilds),
            "members": members_total,
            "active_members": active_members,
            "bots": bots_total,
            "watchlisted": watchlisted,
            "open_cases": open_cases,
            "overdue_cases": overdue_cases,
            "security_risks": critical_security,
            "audit_24h": audit_24h,
            "open_alerts": open_alerts,
            "critical_alerts": critical_alerts,
            "queue_depth": queue_depth,
            "failed_jobs_24h": failed_jobs_24h,
            "successful_jobs_7d": successful_jobs_7d,
            "enabled_plugins": enabled_plugins_total,
        },
        "workers": worker_items,
        "guilds": guild_cards,
    }
