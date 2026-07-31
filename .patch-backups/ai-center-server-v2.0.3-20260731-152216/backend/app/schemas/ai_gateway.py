from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AIProviderCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    provider_type: str
    api_key: str = Field(min_length=1, max_length=10000)
    api_base_url: str | None = None
    organization_id: str | None = None
    project_id: str | None = None
    default_model: str | None = None
    enabled: bool = True
    priority: int = Field(default=100, ge=1, le=10000)
    timeout_seconds: int = Field(default=30, ge=3, le=300)
    max_retries: int = Field(default=1, ge=0, le=10)
    capabilities: list[str] = []
    settings: dict[str, Any] = {}


class AIProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    provider_type: str | None = None
    api_key: str | None = Field(default=None, min_length=1, max_length=10000)
    api_base_url: str | None = None
    organization_id: str | None = None
    project_id: str | None = None
    default_model: str | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=10000)
    timeout_seconds: int | None = Field(default=None, ge=3, le=300)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    capabilities: list[str] | None = None
    settings: dict[str, Any] | None = None


class AIProviderResponse(BaseModel):
    id: UUID
    guild_id: str
    name: str
    provider_type: str
    api_base_url: str | None
    key_hint: str | None
    organization_id: str | None
    project_id: str | None
    default_model: str | None
    enabled: bool
    priority: int
    timeout_seconds: int
    max_retries: int
    capabilities: list[str]
    settings: dict[str, Any]
    last_health_status: str | None
    last_health_latency_ms: int | None
    last_health_check_at: datetime | None
    last_error: str | None
    consecutive_failures: int = 0
    circuit_open_until: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AIProviderTestResponse(BaseModel):
    provider_id: UUID
    status: str
    latency_ms: int
    detail: str


class AIRouteTargetUpsert(BaseModel):
    provider_id: UUID
    position: int = Field(ge=1, le=100)
    model: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=3, le=300)
    retries: int = Field(default=0, ge=0, le=10)
    enabled: bool = True
    configuration: dict[str, Any] = {}


class AIRouteUpsert(BaseModel):
    enabled: bool = True
    max_total_attempts: int = Field(default=6, ge=1, le=50)
    failure_threshold: int = Field(default=3, ge=1, le=20)
    cooldown_seconds: int = Field(default=120, ge=10, le=86400)
    configuration: dict[str, Any] = {}
    targets: list[AIRouteTargetUpsert] = []


class AIRouteTargetResponse(AIRouteTargetUpsert):
    id: UUID


class AIRouteResponse(BaseModel):
    id: UUID
    guild_id: str
    capability: str
    enabled: bool
    max_total_attempts: int
    failure_threshold: int
    cooldown_seconds: int
    configuration: dict[str, Any]
    targets: list[AIRouteTargetResponse]
    created_at: datetime
    updated_at: datetime
