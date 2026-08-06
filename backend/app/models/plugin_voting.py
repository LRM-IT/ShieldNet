from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.core import Base


class VotingPoll(Base):
    __tablename__ = "voting_polls"
    __table_args__ = ({"schema": "discord"},)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    channel_id: Mapped[int | None] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    primary_language: Mapped[str] = mapped_column(String(16), default="en")
    fallback_language: Mapped[str] = mapped_column(String(16), default="en")
    language_selection_mode: Mapped[str] = mapped_column(
        String(32), default="automatic_with_selector"
    )
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    selection_mode: Mapped[str] = mapped_column(String(16), default="single")
    anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_change_vote: Mapped[bool] = mapped_column(Boolean, default=True)
    show_live_results: Mapped[bool] = mapped_column(Boolean, default=True)
    min_choices: Mapped[int] = mapped_column(Integer, default=1)
    max_choices: Mapped[int] = mapped_column(Integer, default=1)
    allowed_role_ids: Mapped[list] = mapped_column(JSONB, default=list)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_template_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("media.templates.id", ondelete="SET NULL")
    )
    result_language: Mapped[str | None] = mapped_column(String(16))
    result_qr_url: Mapped[str | None] = mapped_column(String(1000))
    publish_result_image: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_settings: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    result_message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VotingPollTranslation(Base):
    __tablename__ = "voting_poll_translations"
    __table_args__ = (
        UniqueConstraint("poll_id", "language_code", name="uq_voting_poll_language"),
        {"schema": "discord"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    poll_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("discord.voting_polls.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    completion_message: Mapped[str | None] = mapped_column(Text)
    translation_source: Mapped[str] = mapped_column(String(16), default="manual")
    ai_provider: Mapped[str | None] = mapped_column(String(64))
    ai_model: Mapped[str | None] = mapped_column(String(128))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    translated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VotingOption(Base):
    __tablename__ = "voting_options"
    __table_args__ = (
        UniqueConstraint("poll_id", "position", name="uq_voting_option_position"),
        {"schema": "discord"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    poll_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("discord.voting_polls.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class VotingOptionTranslation(Base):
    __tablename__ = "voting_option_translations"
    __table_args__ = (
        UniqueConstraint("option_id", "language_code", name="uq_voting_option_language"),
        {"schema": "discord"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    option_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("discord.voting_options.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))


class VotingVote(Base):
    __tablename__ = "voting_votes"
    __table_args__ = (
        UniqueConstraint("poll_id", "discord_user_id", "option_id",
                         name="uq_voting_user_option"),
        {"schema": "discord"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    poll_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("discord.voting_polls.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    option_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("discord.voting_options.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    language_code: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VotingPublicationJob(Base):
    __tablename__ = "voting_publication_jobs"
    __table_args__ = ({"schema": "discord"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    poll_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("discord.voting_polls.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
