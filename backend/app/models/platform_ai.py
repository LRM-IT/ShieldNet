import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.core import Base


class PlatformAIProvider(Base):
    __tablename__ = "platform_providers"
    __table_args__ = (
        UniqueConstraint("name", name="uq_ai_platform_provider_name"),
        {"schema": "ai"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    api_base_url: Mapped[str | None] = mapped_column(String(500))
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_hint: Mapped[str | None] = mapped_column(String(32))
    organization_id: Mapped[str | None] = mapped_column(String(255))
    project_id: Mapped[str | None] = mapped_column(String(255))
    default_model: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    last_health_status: Mapped[str | None] = mapped_column(String(32))
    last_health_latency_ms: Mapped[int | None] = mapped_column(Integer)
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PlatformAISettings(Base):
    __tablename__ = "platform_settings"
    __table_args__ = ({"schema": "ai"},)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    defaults: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    limits: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    emergency_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.users.id", ondelete="SET NULL"),
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
