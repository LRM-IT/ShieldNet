from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import User
from app.models.discord import (
    BotStatus,
    Guild,
    GuildMembership,
    GuildStatus,
    MembershipRole,
    MembershipStatus,
)


class GuildRegistryService:
    """Central registry for every Discord guild referenced by ShieldNet.

    All modules must ensure that the guild exists here before inserting rows
    that reference ``discord.guilds.guild_id``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, guild_id: int) -> Guild | None:
        return await self.session.get(Guild, guild_id)

    async def ensure_exists(
        self,
        guild_id: int,
        *,
        name: str | None = None,
        icon_url: str | None = None,
        owner_discord_id: int | None = None,
        member_count: int | None = None,
        bot_online: bool | None = None,
        commit: bool = False,
    ) -> Guild:
        guild = await self.session.get(Guild, guild_id)
        now = datetime.now(UTC)

        if guild is None:
            safe_owner_id = owner_discord_id or 0
            guild = Guild(
                guild_id=guild_id,
                name=(name or f"Discord Server {guild_id}")[:255],
                icon_url=icon_url,
                owner_discord_id=safe_owner_id,
                member_count=max(member_count or 0, 0),
                preferred_language="uk",
                status=(GuildStatus.ACTIVE if bot_online else GuildStatus.INACTIVE),
                bot_status=(
                    BotStatus.ONLINE if bot_online else BotStatus.OFFLINE
                ),
                last_sync_at=now if bot_online else None,
            )
            self.session.add(guild)
            await self.session.flush()
        else:
            if name:
                guild.name = name[:255]
            if icon_url is not None:
                guild.icon_url = icon_url
            if owner_discord_id:
                guild.owner_discord_id = owner_discord_id
            if member_count is not None:
                guild.member_count = max(member_count, 0)
            if bot_online is True:
                guild.bot_status = BotStatus.ONLINE
                guild.left_at = None
                guild.last_sync_at = now
            elif bot_online is False and guild.bot_status == BotStatus.REMOVED:
                guild.bot_status = BotStatus.OFFLINE

        if commit:
            await self.session.commit()
            await self.session.refresh(guild)
        return guild

    async def ensure_management_target(
        self,
        guild_id: int,
        user: User,
    ) -> Guild:
        """Guarantee FK parent row for an authorized management request.

        Superadmins can open a guild before the bot has completed its first
        synchronization. In that case a safe placeholder is created and later
        enriched by OAuth or the bot registration endpoint.
        """
        return await self.ensure_exists(
            guild_id,
            owner_discord_id=user.discord_user_id or 0,
            bot_online=None,
        )

    async def synchronize_oauth_guilds(
        self,
        *,
        user: User,
        discord_user_id: int,
        oauth_guilds: list[dict[str, Any]],
    ) -> None:
        """Synchronize guilds that the Discord user is allowed to manage.

        Discord returns an ``owner`` flag and a permission bitset. ShieldNet
        grants local administrator access to owners and to users with either
        Administrator or Manage Server permission. This keeps normal server
        administrators working after global SuperAdmin access is removed.
        """
        administrator_permission = 0x8
        manage_guild_permission = 0x20

        for item in oauth_guilds:
            raw_id = item.get("id")
            if not raw_id:
                continue

            is_owner = bool(item.get("owner"))
            try:
                permissions = int(item.get("permissions") or 0)
            except (TypeError, ValueError):
                permissions = 0
            can_manage = is_owner or bool(
                permissions & (administrator_permission | manage_guild_permission)
            )
            if not can_manage:
                continue

            guild_id = int(raw_id)
            icon_hash = item.get("icon")
            icon_url = (
                f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png"
                if icon_hash
                else None
            )
            approximate_member_count = item.get("approximate_member_count")

            guild = await self.ensure_exists(
                guild_id,
                name=item.get("name") or f"Discord Server {guild_id}",
                icon_url=icon_url,
                owner_discord_id=discord_user_id if is_owner else None,
                member_count=(
                    int(approximate_member_count)
                    if approximate_member_count is not None
                    else None
                ),
                bot_online=None,
            )

            membership_result = await self.session.execute(
                select(GuildMembership).where(
                    GuildMembership.guild_id == guild.guild_id,
                    GuildMembership.discord_user_id == discord_user_id,
                )
            )
            membership = membership_result.scalar_one_or_none()

            if membership is None:
                self.session.add(
                    GuildMembership(
                        guild_id=guild.guild_id,
                        user_id=user.id,
                        discord_user_id=discord_user_id,
                        role=MembershipRole.ADMIN,
                        status=MembershipStatus.ACTIVE,
                    )
                )
            else:
                membership.user_id = user.id
                membership.role = MembershipRole.ADMIN
                membership.status = MembershipStatus.ACTIVE

        await self.session.flush()
