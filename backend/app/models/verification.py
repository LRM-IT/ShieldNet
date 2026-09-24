import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.core import Base


class VerificationSettings(Base):
    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            name="uq_verification_settings_guild",
        ),
        {"schema": "verification"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "discord.guilds.guild_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    verified_role_id: Mapped[int | None] = mapped_column(
        BigInteger,
    )
    review_channel_id: Mapped[int | None] = mapped_column(
        BigInteger,
    )
    invocation_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    text_commands: Mapped[str] = mapped_column(String(255), nullable=False, server_default="!verify")
    slash_command_name: Mapped[str] = mapped_column(String(32), nullable=False, server_default="verify")
    channel_cleanup_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    nickname_template: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        server_default="[{alliance}] {nickname}",
    )
    auto_approve: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    alliance_min_length: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="2",
    )
    alliance_max_length: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="8",
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "core.users.id",
            ondelete="SET NULL",
        ),
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
        onupdate=func.now(),
    )


class VerificationRequest(Base):
    __tablename__ = "requests"
    __table_args__ = {"schema": "verification"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    guild_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "discord.guilds.guild_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    discord_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    alliance: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    nickname: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    server_number: Mapped[str] = mapped_column(String(32), nullable=False, server_default="")
    requested_nickname: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="pending",
    )
    result_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "core.users.id",
            ondelete="SET NULL",
        ),
    )
    decided_by_discord_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    notification_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="none",
    )
    notification_message: Mapped[str | None] = mapped_column(Text)
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    review_notification_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="pending",
    )
    review_message_id: Mapped[int | None] = mapped_column(BigInteger)
    review_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    evidence_url: Mapped[str | None] = mapped_column(String(1000))
    submitted_language: Mapped[str | None] = mapped_column(String(16))
    applicant_comment: Mapped[str | None] = mapped_column(Text)
    change_request_reason: Mapped[str | None] = mapped_column(Text)
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class VerificationLevel(Base):
    __tablename__ = "levels"
    __table_args__ = (UniqueConstraint("guild_id", "name", name="uq_verification_level_name"), {"schema": "verification"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    channel_id: Mapped[int | None] = mapped_column(BigInteger)
    expected_text: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    role_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    criteria: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    marker: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default='{"x":0,"y":0,"width":1,"height":1}')
    template_path: Mapped[str | None] = mapped_column(String(500))
    template_mime: Mapped[str | None] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class VerificationLevelSubmission(Base):
    __tablename__ = "level_submissions"
    __table_args__ = {"schema": "verification"}
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    level_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verification.levels.id", ondelete="CASCADE"), nullable=False, index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"), nullable=False, index=True)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discord_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    image_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="processing")
    matched: Mapped[bool | None] = mapped_column(Boolean)
    detected_text: Mapped[str | None] = mapped_column(Text)
    ai_result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    result_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VerificationDecision(Base):
    __tablename__ = "decisions"
    __table_args__ = {"schema": "verification"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid())
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verification.requests.id", ondelete="CASCADE"), nullable=False, index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
