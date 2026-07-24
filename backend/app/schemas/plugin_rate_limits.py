from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PluginRateLimitUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limits: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Per-installation limits by Plugin API scope"
        ),
    )


class EffectivePluginRateLimit(BaseModel):
    scope: str
    limit: int
    source: str


class PluginRateLimitSettingsResponse(BaseModel):
    guild_id: int
    plugin_key: str
    installation_limits: dict[str, int]
    manifest_limits: dict[str, int]
    effective_limits: list[EffectivePluginRateLimit]
