import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, computed_field

from app.models.core import User
from app.services.global_access import GlobalAccessService


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    login: str
    display_name: str | None
    avatar_url: str | None
    discord_user_id: int | None
    status: str
    email_verified: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def roles(self) -> list[str]:
        source = getattr(self, "__pydantic_extra__", None)
        return []


def user_to_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "login": user.login,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "discord_user_id": user.discord_user_id,
        "preferred_locale": user.preferred_locale,
        "preferred_timezone": user.preferred_timezone,
        "display_currency": user.display_currency,
        "use_discord_locale": user.use_discord_locale,
        "status": user.status.value,
        "email_verified": user.email_verified,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "roles": GlobalAccessService.effective_role_names(user),
        "highest_role": (GlobalAccessService.highest_role(user).value if GlobalAccessService.highest_role(user) else None),
        "is_superadmin": GlobalAccessService.is_superadmin(user),
    }
