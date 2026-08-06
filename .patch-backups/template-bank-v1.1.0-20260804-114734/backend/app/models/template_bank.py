from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.core import Base


class TemplateBankSettings(Base):
    __tablename__ = "settings"
    __table_args__ = {"schema": "media"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    default_qr_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="https://discord.lrm-it.com", server_default="https://discord.lrm-it.com")
    default_qr_caption: Mapped[str] = mapped_column(String(255), nullable=False, default="Visit our website", server_default="Visit our website")
    allow_guild_qr_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class MediaTemplate(Base):
    __tablename__ = "templates"
    __table_args__ = (UniqueConstraint("key", name="uq_media_templates_key"), {"schema": "media"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    canvas_width: Mapped[int] = mapped_column(Integer, nullable=False)
    canvas_height: Mapped[int] = mapped_column(Integer, nullable=False)
    background_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    preview_path: Mapped[str | None] = mapped_column(String(1000))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
