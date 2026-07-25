import secrets
from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import create_oauth_state, decode_oauth_state
from app.models.core import AuthSource, GlobalRole, PlatformDiscordAdmin, User, UserRole, UserStatus
from app.models.discord import (
    Guild,
    GuildMembership,
    MembershipRole,
    MembershipStatus,
)
from app.services.auth import AuthService
from app.services.guild_registry import GuildRegistryService


class DiscordOAuthService:
    authorize_url = "https://discord.com/oauth2/authorize"
    token_url = "https://discord.com/api/oauth2/token"
    user_url = "https://discord.com/api/v10/users/@me"
    guilds_url = "https://discord.com/api/v10/users/@me/guilds"

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    @property
    def secure_cookie(self) -> bool:
        return settings.environment == "production"

    def create_state(self) -> str:
        self._ensure_configured()
        return create_oauth_state()

    def build_authorization_url(self, state: str) -> str:
        self._ensure_configured()

        query = urlencode(
            {
                "client_id": settings.discord_client_id,
                "response_type": "code",
                "redirect_uri": settings.discord_redirect_uri,
                "scope": settings.discord_oauth_scopes,
                "state": state,
                "prompt": "consent",
            }
        )

        return f"{self.authorize_url}?{query}"

    def verify_state(
        self,
        state: str,
        cookie_state: str | None,
    ) -> None:
        if not cookie_state or not secrets.compare_digest(
            state,
            cookie_state,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth state mismatch",
            )

        decode_oauth_state(state)

    async def authenticate(
        self,
        code: str,
        ip_address: str | None,
        user_agent: str | None,
    ):
        if self.session is None:
            raise RuntimeError("Database session is required.")

        self._ensure_configured()

        profile, oauth_guilds = await self._request_discord_data(code)

        discord_user_id = int(profile["id"])
        email = (profile.get("email") or "").strip().lower()

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discord did not provide an email address",
            )

        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(
                or_(
                    User.discord_user_id == discord_user_id,
                    User.email == email,
                )
            )
        )
        user = result.scalar_one_or_none()

        avatar_hash = profile.get("avatar")
        avatar_url = (
            f"https://cdn.discordapp.com/avatars/"
            f"{discord_user_id}/{avatar_hash}.png"
            if avatar_hash
            else None
        )

        if user is None:
            user = User(
                email=email,
                login=f"discord_{discord_user_id}",
                display_name=(
                    profile.get("global_name")
                    or profile.get("username")
                ),
                avatar_url=avatar_url,
                discord_user_id=discord_user_id,
                status=UserStatus.ACTIVE,
                email_verified=bool(profile.get("verified")),
                last_login_at=datetime.now(UTC),
            )
            self.session.add(user)
            await self.session.flush()
        else:
            user.discord_user_id = discord_user_id
            user.email = email
            user.display_name = (
                profile.get("global_name")
                or profile.get("username")
            )
            user.avatar_url = avatar_url
            user.status = UserStatus.ACTIVE
            user.email_verified = bool(profile.get("verified"))
            user.last_login_at = datetime.now(UTC)

        await self._synchronize_guild_access(
            user=user,
            discord_user_id=discord_user_id,
            oauth_guilds=oauth_guilds,
        )

        # Ensure roles are loaded before generating the ShieldNet access token.
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["roles"])

        auth_service = AuthService(self.session)

        issue_tokens = getattr(auth_service, "issue_tokens", None)
        if issue_tokens is None:
            issue_tokens = getattr(auth_service, "_issue_tokens", None)

        if issue_tokens is None:
            raise RuntimeError(
                "AuthService token issuing method was not found."
            )

        admin_result = await self.session.execute(
            select(PlatformDiscordAdmin).where(
                PlatformDiscordAdmin.discord_user_id == discord_user_id,
                PlatformDiscordAdmin.is_active.is_(True),
                or_(PlatformDiscordAdmin.expires_at.is_(None), PlatformDiscordAdmin.expires_at > datetime.now(UTC)),
            )
        )
        platform_admin = admin_result.scalar_one_or_none()
        auth_source = AuthSource.DISCORD_PLATFORM.value if platform_admin else AuthSource.DISCORD_GUILD.value
        if platform_admin:
            platform_admin.last_login_at = datetime.now(UTC)
            role_value = GlobalRole.ADMIN if platform_admin.role == "platform_admin" else GlobalRole.MODERATOR
            if not any(item.role == role_value for item in user.roles):
                self.session.add(UserRole(user_id=user.id, role=role_value))
                await self.session.flush()
                await self.session.refresh(user, attribute_names=["roles"])

        tokens = await issue_tokens(
            user,
            ip_address,
            user_agent,
            auth_source,
        )

        # Some AuthService versions commit internally; this remains safe.
        await self.session.commit()
        return tokens

    async def _request_discord_data(
        self,
        code: str,
    ) -> tuple[dict, list[dict]]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_response = await client.post(
                self.token_url,
                data={
                    "client_id": settings.discord_client_id,
                    "client_secret": settings.discord_client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.discord_redirect_uri,
                },
                headers={
                    "Content-Type":
                    "application/x-www-form-urlencoded"
                },
            )

            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Discord token exchange failed",
                )

            discord_access_token = token_response.json().get(
                "access_token"
            )

            if not discord_access_token:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Discord access token is missing",
                )

            headers = {
                "Authorization": f"Bearer {discord_access_token}"
            }

            profile_response = await client.get(
                self.user_url,
                headers=headers,
            )
            guilds_response = await client.get(
                self.guilds_url,
                headers=headers,
                params={"with_counts": "true"},
            )

            if profile_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Discord profile request failed",
                )

            if guilds_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Discord guild list request failed",
                )

        return profile_response.json(), guilds_response.json()

    async def _synchronize_guild_access(
        self,
        user: User,
        discord_user_id: int,
        oauth_guilds: list[dict],
    ) -> None:
        registry = GuildRegistryService(self.session)
        await registry.synchronize_oauth_guilds(
            user=user,
            discord_user_id=discord_user_id,
            oauth_guilds=oauth_guilds,
        )

        oauth_ids = {
            int(item["id"])
            for item in oauth_guilds
            if item.get("id")
        }
        if not oauth_ids:
            return

        # Preserve explicitly assigned moderator access and attach it to the
        # authenticated core user when the Discord identity matches.
        memberships_result = await self.session.execute(
            select(GuildMembership).where(
                GuildMembership.guild_id.in_(oauth_ids),
                GuildMembership.discord_user_id == discord_user_id,
            )
        )
        for membership in memberships_result.scalars().all():
            if membership.user_id is None:
                membership.user_id = user.id

    @staticmethod
    def _ensure_configured() -> None:
        if not all(
            (
                settings.discord_client_id,
                settings.discord_client_secret,
                settings.discord_redirect_uri,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Discord OAuth is not configured",
            )
