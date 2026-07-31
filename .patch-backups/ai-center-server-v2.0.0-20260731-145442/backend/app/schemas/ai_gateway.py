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
    max_retries: int = Field(default=2, ge=0, le=10)
    capabilities: list[str] = []
    settings: dict[str, Any] = {}


class AIProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
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
    created_at: datetime
    updated_at: datetime


class AIProviderTestResponse(BaseModel):
    provider_id: UUID
    status: str
    latency_ms: int
    detail: str


class AIModuleSettingUpsert(BaseModel):
    provider_id: UUID | None = None
    model: str | None = None
    fallback_provider_ids: list[UUID] = []
    enabled: bool = True
    configuration: dict[str, Any] = {}


class AIModuleSettingResponse(BaseModel):
    id: UUID
    guild_id: str
    module_key: str
    capability: str
    provider_id: UUID | None
    model: str | None
    fallback_provider_ids: list[str]
    enabled: bool
    configuration: dict[str, Any]
    created_at: datetime
    updated_at: datetime
