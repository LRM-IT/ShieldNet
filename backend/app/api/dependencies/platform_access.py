from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import get_current_user
from app.models.core import User
from app.services.global_access import GlobalAccessService


async def require_platform_viewer(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if getattr(user, "_auth_source", None) == "local_platform":
        GlobalAccessService.require_superadmin(user)
        return user
    if getattr(user, "_auth_source", None) == "discord_platform" and getattr(user, "_platform_role", None) in {
        "platform_admin", "platform_operator", "platform_auditor"
    }:
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform access required")


async def require_platform_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if getattr(user, "_auth_source", None) == "local_platform":
        GlobalAccessService.require_superadmin(user)
        return user
    if getattr(user, "_auth_source", None) == "discord_platform" and getattr(user, "_platform_role", None) == "platform_admin":
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform administrator access required")


async def require_superadmin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    GlobalAccessService.require_superadmin(user)
    return user
