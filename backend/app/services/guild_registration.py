from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import User
from app.models.member_actions import MemberAction, MemberActionType
from app.repositories.settings import SettingsRepository
from app.models.discord import (
    BotStatus,
    Guild,
    GuildMembership,
    GuildStatus,
    MembershipRole,
    MembershipStatus,
)
from app.schemas.discord import GuildRegisterRequest
from app.services.guild_registry import GuildRegistryService


class GuildRegistrationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.registry = GuildRegistryService(session)

    async def register(self, payload: GuildRegisterRequest) -> Guild:
        existing = await self.session.get(Guild, payload.guild_id)
        first_bot_sync = existing is None or existing.last_sync_at is None
        guild = await self.registry.ensure_exists(
            payload.guild_id,
            name=payload.name,
            icon_url=payload.icon_url,
            owner_discord_id=payload.owner_discord_id,
            member_count=payload.member_count,
            bot_online=True,
        )
        guild.preferred_language = payload.preferred_language
        # A successful bot synchronization is the complete server connection.
        # Plugin configuration and the optional setup wizard must not affect the
        # guild connection status.
        guild.status = GuildStatus.ACTIVE
        guild.bot_status = BotStatus.ONLINE
        guild.left_at = None
        guild.last_sync_at = datetime.now(UTC)

        owner = (
            await self.session.execute(
                select(User).where(
                    User.discord_user_id == payload.owner_discord_id
                )
            )
        ).scalar_one_or_none()

        membership = (
            await self.session.execute(
                select(GuildMembership).where(
                    GuildMembership.guild_id == payload.guild_id,
                    GuildMembership.discord_user_id
                    == payload.owner_discord_id,
                )
            )
        ).scalar_one_or_none()

        membership_status = (
            MembershipStatus.ACTIVE
            if owner
            else MembershipStatus.PENDING
        )

        if membership is None:
            self.session.add(
                GuildMembership(
                    guild_id=payload.guild_id,
                    user_id=owner.id if owner else None,
                    discord_user_id=payload.owner_discord_id,
                    role=MembershipRole.ADMIN,
                    status=membership_status,
                )
            )
        else:
            membership.user_id = owner.id if owner else None
            membership.role = MembershipRole.ADMIN
            membership.status = membership_status

        if first_bot_sync:
            settings = {
                row.key: row.value
                for row in await SettingsRepository(self.session).list_module(0, "owner_support_invite")
            }
            invite_url = str(settings.get("invite_url") or "").strip()
            if bool(settings.get("enabled")) and invite_url:
                marker = await SettingsRepository(self.session).get(
                    payload.guild_id, "owner_support_invite", "sent"
                )
                if marker is None:
                    message = str(settings.get("message") or "Welcome! Join our Discord support server for help and updates.").strip()
                    content = message if invite_url in message else f"{message}\n\n{invite_url}"
                    self.session.add(MemberAction(
                        guild_id=payload.guild_id,
                        discord_user_id=payload.owner_discord_id,
                        action_type=MemberActionType.SEND_DM,
                        payload={"message": content, "source": "owner_support_invite"},
                        requested_by=None,
                    ))
                    await SettingsRepository(self.session).upsert(
                        guild_id=payload.guild_id,
                        module="owner_support_invite",
                        key="sent",
                        value={"owner_discord_id": str(payload.owner_discord_id), "invite_url": invite_url, "queued_at": datetime.now(UTC).isoformat()},
                        value_type="object",
                        updated_by=None,
                    )

        await self.session.commit()
        await self.session.refresh(guild)
        return guild

    async def mark_left(self, guild_id: int) -> None:
        guild = await self.session.get(Guild, guild_id)
        if guild:
            guild.status = GuildStatus.LEFT
            guild.bot_status = BotStatus.REMOVED
            guild.left_at = datetime.now(UTC)
            await self.session.commit()
