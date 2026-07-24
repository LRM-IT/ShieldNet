from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PluginUsageStatusCount(BaseModel):
    status_code: int
    requests: int


class PluginUsageScopeCount(BaseModel):
    scope: str
    requests: int


class PluginUsageSummaryResponse(BaseModel):
    guild_id: int
    plugin_key: str

    requests_today: int
    requests_total: int

    successful_today: int
    successful_total: int

    errors_today: int
    errors_total: int

    rate_limited_today: int
    rate_limited_total: int

    average_duration_ms_today: float
    average_duration_ms_total: float

    last_request_at: datetime | None

    status_breakdown_today: list[
        PluginUsageStatusCount
    ] = Field(default_factory=list)

    scope_breakdown_today: list[
        PluginUsageScopeCount
    ] = Field(default_factory=list)

    generated_at: datetime


class PluginUsageHistoryPoint(BaseModel):
    day: date
    requests: int
    successful: int
    errors: int
    rate_limited: int
    average_duration_ms: float


class PluginUsageHistoryResponse(BaseModel):
    guild_id: int
    plugin_key: str
    days: int
    points: list[PluginUsageHistoryPoint]
    generated_at: datetime
