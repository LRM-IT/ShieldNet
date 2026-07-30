from __future__ import annotations

import re
from pydantic import BaseModel, Field, field_validator, model_validator

COMMAND_RE = re.compile(r"^[a-z0-9_-]{1,32}$")


class SettingsPayload(BaseModel):
    enabled: bool = True
    verification_channel_id: int | None = None
    verified_role_id: int | None = None
    log_channel_id: int | None = None

    nickname_mask: str = Field(default="[{ALLIANCE}] {NICKNAME}", max_length=128)
    allow_reverification: bool = True
    alliance_uppercase: bool = True
    trim_values: bool = True
    max_alliance_length: int = Field(default=16, ge=1, le=64)
    max_nickname_length: int = Field(default=24, ge=1, le=64)

    verification_message: str = Field(
        default="Натисніть кнопку нижче, щоб пройти верифікацію.", max_length=2000
    )
    verification_button_text: str = Field(default="Пройти верифікацію", max_length=80)

    slash_verify_enabled: bool = True
    slash_verify_name: str = "verify"
    prefix_verify_enabled: bool = True
    command_prefix: str = Field(default="!", min_length=1, max_length=8)
    prefix_verify_name: str = "verify"

    slash_rename_enabled: bool = True
    slash_rename_name: str = "rename"
    prefix_rename_enabled: bool = True
    prefix_rename_name: str = "rename"

    allowed_channel_ids: list[int] = Field(default_factory=list)
    delete_user_command: bool = True
    cooldown_seconds: int = Field(default=30, ge=0, le=86400)

    assign_role_on_verify: bool = True
    assign_role_on_rename: bool = True

    success_message_enabled: bool = True
    success_message_text: str = Field(
        default="🎉 {MENTION}, вас успішно верифіковано!", max_length=2000
    )
    success_message_delete_after: int = Field(default=300, ge=0, le=86400)

    @field_validator(
        "slash_verify_name",
        "prefix_verify_name",
        "slash_rename_name",
        "prefix_rename_name",
    )
    @classmethod
    def validate_command(cls, value: str) -> str:
        value = value.strip().lower()
        if not COMMAND_RE.fullmatch(value):
            raise ValueError("Command may contain only a-z, 0-9, underscore and hyphen")
        return value

    @model_validator(mode="after")
    def validate_mask(self):
        allowed = {"{ALLIANCE}", "{NICKNAME}"}
        if "{NICKNAME}" not in self.nickname_mask:
            raise ValueError("nickname_mask must contain {NICKNAME}")
        tokens = set(re.findall(r"\{[A-Z_]+\}", self.nickname_mask))
        unknown = tokens - allowed
        if unknown:
            raise ValueError(f"Unknown mask tokens: {', '.join(sorted(unknown))}")
        return self


class ManualVerificationPayload(BaseModel):
    user_id: int
    alliance: str = Field(min_length=1, max_length=64)
    nickname: str = Field(min_length=1, max_length=64)


class MemberUpdatePayload(BaseModel):
    alliance: str | None = Field(default=None, min_length=1, max_length=64)
    nickname: str | None = Field(default=None, min_length=1, max_length=64)
