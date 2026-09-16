import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
import re


class VerificationSettingsInput(BaseModel):
    enabled: bool = False
    verified_role_id: int | None = None
    review_channel_id: int | None = None
    invocation_channel_id: int | None = None
    text_commands: str = Field(default="!verify", max_length=255)
    slash_command_name: str = Field(default="verify", min_length=1, max_length=32)
    nickname_template: str = Field(
        default="[{alliance}] {nickname}",
        min_length=3,
        max_length=128,
    )
    auto_approve: bool = False
    alliance_min_length: int = Field(
        default=2,
        ge=1,
        le=16,
    )
    alliance_max_length: int = Field(
        default=8,
        ge=1,
        le=32,
    )

    @field_validator("text_commands")
    @classmethod
    def valid_commands(cls, value: str) -> str:
        commands = [item.strip().lower() for item in value.replace("\n", ",").split(",") if item.strip()]
        if len(commands) > 10 or any(not command.startswith(("!", ".", "?")) or " " in command or len(command) > 32 for command in commands):
            raise ValueError("Use up to 10 comma-separated commands beginning with !, . or ?")
        return ",".join(dict.fromkeys(commands))

    @field_validator("slash_command_name")
    @classmethod
    def valid_slash_command(cls, value: str) -> str:
        value = value.strip().lower().lstrip("/")
        if not re.fullmatch(r"[a-z0-9_-]{1,32}", value):
            raise ValueError("Slash command may contain lowercase Latin letters, digits, _ and -")
        return value

    @field_validator("nickname_template")
    @classmethod
    def valid_nickname_template(cls, value: str) -> str:
        try:
            value.format(alliance="A", nickname="Player", server="1")
        except (KeyError, ValueError) as exc:
            raise ValueError("Use only {alliance}, {nickname} and {server}") from exc
        return value


class VerificationRequestCreate(BaseModel):
    discord_user_id: int
    alliance: str = Field(
        min_length=1,
        max_length=32,
    )
    nickname: str = Field(
        min_length=1,
        max_length=64,
    )
    server_number: str = Field(min_length=1, max_length=32)


class VerificationDecisionInput(BaseModel):
    reason: str | None = Field(
        default=None,
        max_length=1000,
    )


class VerificationRequestResult(BaseModel):
    status: str = Field(
        pattern="^(completed|failed)$",
    )
    result_message: str | None = Field(
        default=None,
        max_length=2000,
    )


class VerificationRequestResponse(BaseModel):
    id: uuid.UUID
    guild_id: int
    discord_user_id: int
    alliance: str
    nickname: str
    requested_nickname: str
    status: str
    result_message: str | None
    decision_reason: str | None
    decided_at: datetime | None
    processed_at: datetime | None
    created_at: datetime



class VerificationBulkInput(BaseModel):
    request_ids: list[uuid.UUID] = Field(
        min_length=1,
        max_length=200,
    )


class VerificationRecoverInput(BaseModel):
    older_than_minutes: int = Field(
        default=10,
        ge=1,
        le=1440,
    )


class VerificationChangesInput(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class VerificationResubmitInput(BaseModel):
    alliance: str = Field(min_length=1, max_length=32)
    nickname: str = Field(min_length=1, max_length=64)
    evidence_url: str | None = Field(default=None, max_length=1000)
    submitted_language: str | None = Field(default=None, max_length=16)
    applicant_comment: str | None = Field(default=None, max_length=2000)
