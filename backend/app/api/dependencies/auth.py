from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.core import PlatformDiscordAdmin, User, UserStatus

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is unavailable",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_source = payload.get("auth_source", "discord_guild")
    setattr(user, "_auth_source", auth_source)
    setattr(user, "_platform_role", None)

    # A Discord platform grant is checked on every authenticated request.
    # Disabling or expiring the grant therefore takes effect immediately,
    # without waiting for the access token to expire.
    if auth_source == "discord_platform" and user.discord_user_id is not None:
        grant = await session.scalar(
            select(PlatformDiscordAdmin).where(
                PlatformDiscordAdmin.discord_user_id == user.discord_user_id,
                PlatformDiscordAdmin.is_active.is_(True),
                or_(
                    PlatformDiscordAdmin.expires_at.is_(None),
                    PlatformDiscordAdmin.expires_at > datetime.now(UTC),
                ),
            )
        )
        if grant is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Discord platform access has been revoked or expired",
            )
        setattr(user, "_platform_role", grant.role)

    return user
