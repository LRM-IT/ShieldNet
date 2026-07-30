from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class VerificationSettings(Base):
    __tablename__ = "verification_level1_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_channel_id: Mapped[int | None] = mapped_column(BigInteger)
    verified_role_id: Mapped[int | None] = mapped_column(BigInteger)
    log_channel_id: Mapped[int | None] = mapped_column(BigInteger)

    nickname_mask: Mapped[str] = mapped_column(String(128), default="[{ALLIANCE}] {NICKNAME}")
    allow_reverification: Mapped[bool] = mapped_column(Boolean, default=True)
    alliance_uppercase: Mapped[bool] = mapped_column(Boolean, default=True)
    trim_values: Mapped[bool] = mapped_column(Boolean, default=True)
    max_alliance_length: Mapped[int] = mapped_column(Integer, default=16)
    max_nickname_length: Mapped[int] = mapped_column(Integer, default=24)

    verification_message: Mapped[str] = mapped_column(
        Text, default="Натисніть кнопку нижче, щоб пройти верифікацію."
    )
    verification_button_text: Mapped[str] = mapped_column(String(80), default="Пройти верифікацію")

    slash_verify_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    slash_verify_name: Mapped[str] = mapped_column(String(32), default="verify")
    prefix_verify_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    command_prefix: Mapped[str] = mapped_column(String(8), default="!")
    prefix_verify_name: Mapped[str] = mapped_column(String(32), default="verify")

    slash_rename_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    slash_rename_name: Mapped[str] = mapped_column(String(32), default="rename")
    prefix_rename_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    prefix_rename_name: Mapped[str] = mapped_column(String(32), default="rename")

    allowed_channel_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    delete_user_command: Mapped[bool] = mapped_column(Boolean, default=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=30)

    assign_role_on_verify: Mapped[bool] = mapped_column(Boolean, default=True)
    assign_role_on_rename: Mapped[bool] = mapped_column(Boolean, default=True)

    success_message_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    success_message_text: Mapped[str] = mapped_column(
        Text, default="🎉 {MENTION}, вас успішно верифіковано!"
    )
    success_message_delete_after: Mapped[int] = mapped_column(Integer, default=300)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VerifiedMember(Base):
    __tablename__ = "verification_level1_members"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    discord_name: Mapped[str] = mapped_column(String(255))
    alliance: Mapped[str] = mapped_column(String(64))
    nickname: Mapped[str] = mapped_column(String(64))
    rendered_nickname: Mapped[str | None] = mapped_column(String(64))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    verified_by: Mapped[str] = mapped_column(String(32), default="self")


class VerificationAudit(Base):
    __tablename__ = "verification_level1_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(64))
    old_alliance: Mapped[str | None] = mapped_column(String(64))
    new_alliance: Mapped[str | None] = mapped_column(String(64))
    old_nickname: Mapped[str | None] = mapped_column(String(64))
    new_nickname: Mapped[str | None] = mapped_column(String(64))
    old_rendered_nickname: Mapped[str | None] = mapped_column(String(64))
    new_rendered_nickname: Mapped[str | None] = mapped_column(String(64))
    role_id: Mapped[int | None] = mapped_column(BigInteger)
    role_assigned: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
