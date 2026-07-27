from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.core import Base


class PluginMigrationRecord(Base):
    """Persistent history for ShieldNet plugin SQL migrations."""

    __tablename__ = "plugin_migrations"
    __table_args__ = (
        UniqueConstraint(
            "plugin_key",
            "migration_filename",
            name="uq_plugins_plugin_migrations_key_filename",
        ),
        {"schema": "plugins"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    plugin_key: Mapped[str] = mapped_column(
        String(96),
        nullable=False,
        index=True,
    )
    plugin_version: Mapped[str | None] = mapped_column(String(40))
    migration_order: Mapped[int] = mapped_column(Integer, nullable=False)
    migration_filename: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )
    checksum_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="applied",
        server_default="applied",
    )
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "plugins.install_jobs.id",
            ondelete="SET NULL",
        ),
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
