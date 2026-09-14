from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field

GuildPluginStatus = Literal["installed","enabled","disabled","error"]

class GuildPluginInstallationResponse(BaseModel):
    id: UUID
    guild_id: int
    plugin_key: str
    status: GuildPluginStatus
    enabled: bool
    configuration: dict[str, Any] = Field(default_factory=dict)
    installed_by_user_id: UUID | None = None
    installed_at: datetime
    enabled_at: datetime | None = None
    disabled_at: datetime | None = None
    last_health_check_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

class GuildPluginMarketplaceItemResponse(BaseModel):
    plugin_key: str
    name: str
    version: str | None = None
    summary: str | None = None
    category: str
    icon_url: str | None = None
    verified: bool
    installed: bool
    enabled: bool
    installation_status: str | None = None

class GuildPluginSettingsUpdate(BaseModel):
    configuration: dict[str, Any] = Field(default_factory=dict)
