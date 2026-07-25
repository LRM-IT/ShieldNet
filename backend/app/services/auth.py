from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.models.core import AuthSource, GlobalRole, LoginAttempt, Session, User, UserStatus
from app.schemas.auth import TokenPair


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def login(
        self,
        identity: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        normalized = identity.strip().lower()

        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(
                or_(
                    User.email == normalized,
                    User.login == normalized,
                )
            )
        )
        user = result.scalar_one_or_none()

        valid = (
            user is not None
            and user.password_hash is not None
            and verify_password(password, user.password_hash)
        )

        self.session.add(
            LoginAttempt(
                email=normalized if "@" in normalized else None,
                user_id=user.id if user else None,
                ip_address=ip_address,
                user_agent=user_agent,
                successful=valid,
                failure_reason=None if valid else "invalid_credentials",
            )
        )

        if not valid:
            await self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid login or password",
            )

        if user.status != UserStatus.ACTIVE:
            await self.session.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active",
            )

        user.last_login_at = datetime.now(UTC)
        tokens = await self._issue_tokens(user, ip_address, user_agent, AuthSource.LOCAL_PLATFORM.value)
        await self.session.commit()
        return tokens

    async def platform_login(
        self, identity: str, password: str, ip_address: str | None, user_agent: str | None
    ) -> TokenPair:
        normalized = identity.strip().lower()
        now = datetime.now(UTC)
        window_start = now - timedelta(minutes=15)
        throttle_conditions = []
        if "@" in normalized:
            throttle_conditions.append(LoginAttempt.email == normalized)
        if ip_address:
            throttle_conditions.append(LoginAttempt.ip_address == ip_address)
        failed_attempts = 0
        if throttle_conditions:
            failed_attempts = await self.session.scalar(
                select(func.count(LoginAttempt.id)).where(
                    LoginAttempt.created_at >= window_start,
                    LoginAttempt.successful.is_(False),
                    or_(*throttle_conditions),
                )
            )
        if (failed_attempts or 0) >= 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed platform login attempts. Try again in 15 minutes.",
            )
        result = await self.session.execute(
            select(User).options(selectinload(User.roles)).where(or_(User.email == normalized, User.login == normalized))
        )
        user = result.scalar_one_or_none()
        valid = user is not None and user.password_hash is not None and verify_password(password, user.password_hash)
        is_owner = valid and any(role.role == GlobalRole.SUPERADMIN for role in user.roles)
        self.session.add(LoginAttempt(email=normalized if "@" in normalized else None, user_id=user.id if user else None, ip_address=ip_address, user_agent=user_agent, successful=bool(is_owner), failure_reason=None if is_owner else "platform_access_denied"))
        if not is_owner:
            await self.session.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid platform credentials")
        if user.status != UserStatus.ACTIVE:
            await self.session.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")
        user.last_login_at = datetime.now(UTC)
        tokens = await self._issue_tokens(user, ip_address, user_agent, AuthSource.LOCAL_PLATFORM.value)
        await self.session.commit()
        return tokens

    async def refresh(
        self,
        refresh_token: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        token_hash = hash_refresh_token(refresh_token)
        now = datetime.now(UTC)

        result = await self.session.execute(
            select(Session)
            .options(selectinload(Session.user).selectinload(User.roles))
            .where(
                Session.token_hash == token_hash,
                Session.revoked_at.is_(None),
                Session.expires_at > now,
            )
        )
        stored = result.scalar_one_or_none()

        if stored is None or stored.user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        stored.revoked_at = now
        tokens = await self._issue_tokens(
            stored.user,
            ip_address,
            user_agent,
            stored.auth_source,
        )
        await self.session.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        token_hash = hash_refresh_token(refresh_token)

        result = await self.session.execute(
            select(Session).where(Session.token_hash == token_hash)
        )
        stored = result.scalar_one_or_none()

        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def _issue_tokens(
        self,
        user: User,
        ip_address: str | None,
        user_agent: str | None,
        auth_source: str = AuthSource.DISCORD_GUILD.value,
    ) -> TokenPair:
        roles = [role.role.value for role in user.roles]
        access_token = create_access_token(str(user.id), roles, auth_source)
        refresh_token = generate_refresh_token()

        self.session.add(
            Session(
                user_id=user.id,
                token_hash=hash_refresh_token(refresh_token),
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=datetime.now(UTC)
                + timedelta(days=settings.refresh_token_days),
                auth_source=auth_source,
            )
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_minutes * 60,
        )
