from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from app.db.session import AsyncSessionFactory


class PluginUsageError(ValueError):
    pass


class PluginUsageService:
    @staticmethod
    async def _installation_exists(
        *,
        guild_id: int,
        plugin_key: str,
    ) -> bool:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM plugins.guild_installations
                        WHERE guild_id = :guild_id
                          AND plugin_key = :plugin_key
                    )
                """),
                {
                    "guild_id": guild_id,
                    "plugin_key": plugin_key,
                },
            )

            return bool(result.scalar_one())

    @classmethod
    async def get_summary(
        cls,
        *,
        guild_id: int,
        plugin_key: str,
    ) -> dict[str, Any]:
        if not await cls._installation_exists(
            guild_id=guild_id,
            plugin_key=plugin_key,
        ):
            raise PluginUsageError(
                "Plugin installation was not found"
            )

        async with AsyncSessionFactory() as session:
            summary_result = await session.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (
                            WHERE created_at >=
                                date_trunc(
                                    'day',
                                    NOW()
                                )
                        )::bigint
                            AS requests_today,

                        COUNT(*)::bigint
                            AS requests_total,

                        COUNT(*) FILTER (
                            WHERE created_at >=
                                date_trunc(
                                    'day',
                                    NOW()
                                )
                              AND status_code
                                  BETWEEN 200 AND 399
                        )::bigint
                            AS successful_today,

                        COUNT(*) FILTER (
                            WHERE status_code
                                BETWEEN 200 AND 399
                        )::bigint
                            AS successful_total,

                        COUNT(*) FILTER (
                            WHERE created_at >=
                                date_trunc(
                                    'day',
                                    NOW()
                                )
                              AND status_code >= 400
                        )::bigint
                            AS errors_today,

                        COUNT(*) FILTER (
                            WHERE status_code >= 400
                        )::bigint
                            AS errors_total,

                        COUNT(*) FILTER (
                            WHERE created_at >=
                                date_trunc(
                                    'day',
                                    NOW()
                                )
                              AND status_code = 429
                        )::bigint
                            AS rate_limited_today,

                        COUNT(*) FILTER (
                            WHERE status_code = 429
                        )::bigint
                            AS rate_limited_total,

                        COALESCE(
                            AVG(duration_ms) FILTER (
                                WHERE created_at >=
                                    date_trunc(
                                        'day',
                                        NOW()
                                    )
                            ),
                            0
                        )::float
                            AS average_duration_ms_today,

                        COALESCE(
                            AVG(duration_ms),
                            0
                        )::float
                            AS average_duration_ms_total,

                        MAX(created_at)
                            AS last_request_at
                    FROM plugins.api_audit_logs
                    WHERE guild_id = :guild_id
                      AND plugin_key = :plugin_key
                """),
                {
                    "guild_id": guild_id,
                    "plugin_key": plugin_key,
                },
            )

            summary = dict(
                summary_result.mappings().one()
            )

            status_result = await session.execute(
                text("""
                    SELECT
                        status_code,
                        COUNT(*)::bigint AS requests
                    FROM plugins.api_audit_logs
                    WHERE guild_id = :guild_id
                      AND plugin_key = :plugin_key
                      AND created_at >=
                          date_trunc(
                              'day',
                              NOW()
                          )
                    GROUP BY status_code
                    ORDER BY status_code
                """),
                {
                    "guild_id": guild_id,
                    "plugin_key": plugin_key,
                },
            )

            scope_result = await session.execute(
                text("""
                    SELECT
                        COALESCE(
                            capability,
                            CASE
                                WHEN path LIKE
                                    '%/token/refresh'
                                    THEN
                                        'runtime.token.refresh'
                                WHEN path LIKE
                                    '%/context'
                                    THEN
                                        'runtime.context'
                                ELSE
                                    'unscoped'
                            END
                        ) AS scope,
                        COUNT(*)::bigint AS requests
                    FROM plugins.api_audit_logs
                    WHERE guild_id = :guild_id
                      AND plugin_key = :plugin_key
                      AND created_at >=
                          date_trunc(
                              'day',
                              NOW()
                          )
                    GROUP BY 1
                    ORDER BY requests DESC, scope
                """),
                {
                    "guild_id": guild_id,
                    "plugin_key": plugin_key,
                },
            )

        return {
            "guild_id": guild_id,
            "plugin_key": plugin_key,
            **summary,
            "average_duration_ms_today": round(
                summary[
                    "average_duration_ms_today"
                ],
                2,
            ),
            "average_duration_ms_total": round(
                summary[
                    "average_duration_ms_total"
                ],
                2,
            ),
            "status_breakdown_today": [
                dict(row)
                for row in status_result.mappings()
            ],
            "scope_breakdown_today": [
                dict(row)
                for row in scope_result.mappings()
            ],
            "generated_at": datetime.now(UTC),
        }

    @classmethod
    async def get_history(
        cls,
        *,
        guild_id: int,
        plugin_key: str,
        days: int,
    ) -> dict[str, Any]:
        if days not in {7, 30, 90}:
            raise PluginUsageError(
                "History period must be 7, 30 or 90 days"
            )

        if not await cls._installation_exists(
            guild_id=guild_id,
            plugin_key=plugin_key,
        ):
            raise PluginUsageError(
                "Plugin installation was not found"
            )

        async with AsyncSessionFactory() as session:
            result = await session.execute(
                text("""
                    WITH days AS (
                        SELECT generate_series(
                            CURRENT_DATE
                                - (:days - 1),
                            CURRENT_DATE,
                            INTERVAL '1 day'
                        )::date AS day
                    ),
                    usage AS (
                        SELECT
                            created_at::date AS day,
                            COUNT(*)::bigint
                                AS requests,
                            COUNT(*) FILTER (
                                WHERE status_code
                                    BETWEEN 200 AND 399
                            )::bigint
                                AS successful,
                            COUNT(*) FILTER (
                                WHERE status_code >= 400
                            )::bigint
                                AS errors,
                            COUNT(*) FILTER (
                                WHERE status_code = 429
                            )::bigint
                                AS rate_limited,
                            COALESCE(
                                AVG(duration_ms),
                                0
                            )::float
                                AS average_duration_ms
                        FROM plugins.api_audit_logs
                        WHERE guild_id = :guild_id
                          AND plugin_key = :plugin_key
                          AND created_at >=
                              CURRENT_DATE
                              - (:days - 1)
                        GROUP BY created_at::date
                    )
                    SELECT
                        days.day,
                        COALESCE(
                            usage.requests,
                            0
                        )::bigint AS requests,
                        COALESCE(
                            usage.successful,
                            0
                        )::bigint AS successful,
                        COALESCE(
                            usage.errors,
                            0
                        )::bigint AS errors,
                        COALESCE(
                            usage.rate_limited,
                            0
                        )::bigint AS rate_limited,
                        COALESCE(
                            usage.average_duration_ms,
                            0
                        )::float
                            AS average_duration_ms
                    FROM days
                    LEFT JOIN usage
                      ON usage.day = days.day
                    ORDER BY days.day
                """),
                {
                    "guild_id": guild_id,
                    "plugin_key": plugin_key,
                    "days": days,
                },
            )

            points = []

            for row in result.mappings():
                item = dict(row)
                item["average_duration_ms"] = round(
                    item["average_duration_ms"],
                    2,
                )
                points.append(item)

        return {
            "guild_id": guild_id,
            "plugin_key": plugin_key,
            "days": days,
            "points": points,
            "generated_at": datetime.now(UTC),
        }
