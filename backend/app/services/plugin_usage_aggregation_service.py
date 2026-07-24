from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import text

from app.db.session import AsyncSessionFactory


logger = logging.getLogger(
    "shieldnet.plugin_usage.aggregation"
)


@dataclass(frozen=True, slots=True)
class PluginUsageAggregationResult:
    aggregated_day: date
    aggregate_rows: int
    deleted_audit_rows: int


class PluginUsageAggregationService:
    def __init__(self) -> None:
        self.audit_retention_days = int(
            os.getenv(
                "PLUGIN_AUDIT_RETENTION_DAYS",
                "90",
            )
        )

        self.aggregate_retention_days = int(
            os.getenv(
                "PLUGIN_USAGE_RETENTION_DAYS",
                "730",
            )
        )

        if self.audit_retention_days < 7:
            raise RuntimeError(
                "PLUGIN_AUDIT_RETENTION_DAYS "
                "must be at least 7"
            )

        if self.aggregate_retention_days < 90:
            raise RuntimeError(
                "PLUGIN_USAGE_RETENTION_DAYS "
                "must be at least 90"
            )

    async def aggregate_day(
        self,
        target_day: date,
    ) -> int:
        day_start = datetime.combine(
            target_day,
            datetime.min.time(),
            tzinfo=UTC,
        )

        day_end = day_start + timedelta(days=1)

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text("""
                    INSERT INTO plugins.usage_daily (
                        day,
                        guild_id,
                        plugin_key,
                        requests,
                        successful,
                        errors,
                        rate_limited,
                        duration_total_ms,
                        maximum_duration_ms,
                        updated_at
                    )
                    SELECT
                        :target_day,
                        guild_id,
                        plugin_key,
                        COUNT(*)::bigint,
                        COUNT(*) FILTER (
                            WHERE status_code
                                BETWEEN 200 AND 399
                        )::bigint,
                        COUNT(*) FILTER (
                            WHERE status_code >= 400
                        )::bigint,
                        COUNT(*) FILTER (
                            WHERE status_code = 429
                        )::bigint,
                        COALESCE(
                            SUM(duration_ms),
                            0
                        )::bigint,
                        COALESCE(
                            MAX(duration_ms),
                            0
                        )::integer,
                        NOW()
                    FROM plugins.api_audit_logs
                    WHERE created_at >= :day_start
                      AND created_at < :day_end
                      AND guild_id IS NOT NULL
                      AND plugin_key IS NOT NULL
                    GROUP BY
                        guild_id,
                        plugin_key
                    ON CONFLICT (
                        day,
                        guild_id,
                        plugin_key
                    )
                    DO UPDATE SET
                        requests = EXCLUDED.requests,
                        successful = EXCLUDED.successful,
                        errors = EXCLUDED.errors,
                        rate_limited = EXCLUDED.rate_limited,
                        duration_total_ms =
                            EXCLUDED.duration_total_ms,
                        maximum_duration_ms =
                            EXCLUDED.maximum_duration_ms,
                        updated_at = NOW()
                    RETURNING 1
                """),
                {
                    "target_day": target_day,
                    "day_start": day_start,
                    "day_end": day_end,
                },
            )

            rows = len(result.all())
            await session.commit()

        return rows

    async def cleanup(self) -> tuple[int, int]:
        audit_cutoff = datetime.now(UTC) - timedelta(
            days=self.audit_retention_days
        )

        usage_cutoff = date.today() - timedelta(
            days=self.aggregate_retention_days
        )

        async with AsyncSessionFactory() as session:
            audit_result = await session.execute(
                text("""
                    DELETE FROM plugins.api_audit_logs
                    WHERE created_at < :cutoff
                """),
                {"cutoff": audit_cutoff},
            )

            usage_result = await session.execute(
                text("""
                    DELETE FROM plugins.usage_daily
                    WHERE day < :cutoff
                """),
                {"cutoff": usage_cutoff},
            )

            await session.commit()

        return (
            max(audit_result.rowcount or 0, 0),
            max(usage_result.rowcount or 0, 0),
        )

    async def run_daily(
        self,
    ) -> PluginUsageAggregationResult:
        yesterday = (
            datetime.now(UTC).date()
            - timedelta(days=1)
        )

        aggregate_rows = await self.aggregate_day(
            yesterday
        )

        deleted_audit_rows, deleted_usage_rows = (
            await self.cleanup()
        )

        logger.info(
            "Plugin usage aggregation completed "
            "day=%s aggregates=%s "
            "deleted_audit=%s deleted_usage=%s",
            yesterday,
            aggregate_rows,
            deleted_audit_rows,
            deleted_usage_rows,
        )

        return PluginUsageAggregationResult(
            aggregated_day=yesterday,
            aggregate_rows=aggregate_rows,
            deleted_audit_rows=deleted_audit_rows,
        )


plugin_usage_aggregation_service = (
    PluginUsageAggregationService()
)
