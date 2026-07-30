from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any

import discord
from discord import app_commands
from sqlalchemy import select

from backend.db import SessionLocal
from backend.models import VerificationSettings, VerifiedMember
from backend.service import add_audit, get_or_create_settings, render_nickname, upsert_member

PLUGIN_ID = "verification_level1"
_SLASH_NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")


@dataclass(slots=True)
class Result:
    ok: bool
    message: str
    rendered_nickname: str | None = None
    role_assigned: bool = False


class VerificationModal(discord.ui.Modal):
    def __init__(self, runtime: "VerificationRuntime", guild_id: int):
        super().__init__(title="Verification")
        self.runtime = runtime
        self.guild_id = guild_id

        self.alliance = discord.ui.TextInput(
            label="Alliance",
            placeholder="EVEX",
            min_length=1,
            max_length=64,
        )
        self.nickname = discord.ui.TextInput(
            label="Nickname",
            placeholder="Roman",
            min_length=1,
            max_length=64,
        )
        self.add_item(self.alliance)
        self.add_item(self.nickname)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        result = await self.runtime.apply_profile(
            member=interaction.user,
            alliance=str(self.alliance.value),
            nickname=str(self.nickname.value),
            action="verify",
            actor_user_id=interaction.user.id,
        )
        await interaction.followup.send(result.message, ephemeral=True)


class VerificationView(discord.ui.View):
    def __init__(self, runtime: "VerificationRuntime", guild_id: int, button_text: str):
        super().__init__(timeout=None)
        self.runtime = runtime
        self.guild_id = guild_id

        button = discord.ui.Button(
            label=button_text[:80],
            style=discord.ButtonStyle.success,
            custom_id=f"{PLUGIN_ID}:verify:{guild_id}",
        )
        button.callback = self._open_modal
        self.add_item(button)

    async def _open_modal(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Guild only.", ephemeral=True)
            return
        await interaction.response.send_modal(VerificationModal(self.runtime, interaction.guild.id))


class VerificationRuntime:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.cooldowns: dict[tuple[int, int], float] = {}
        self.dynamic_commands: dict[int, list[app_commands.Command]] = {}

    async def start(self):
        self.bot.add_listener(self.on_message, "on_message")
        self.bot.add_listener(self.on_ready, "on_ready")

    async def stop(self):
        self.bot.remove_listener(self.on_message, "on_message")
        self.bot.remove_listener(self.on_ready, "on_ready")

    async def on_ready(self):
        for guild in self.bot.guilds:
            try:
                await self.register_guild_commands(guild)
            except Exception:
                pass

    async def settings(self, guild_id: int) -> VerificationSettings:
        async with SessionLocal() as session:
            return await get_or_create_settings(session, guild_id)

    def channel_allowed(self, settings: VerificationSettings, channel_id: int) -> bool:
        ids = [int(x) for x in (settings.allowed_channel_ids or [])]
        return not ids or channel_id in ids

    def cooldown_ok(self, settings: VerificationSettings, guild_id: int, user_id: int) -> tuple[bool, int]:
        if settings.cooldown_seconds <= 0:
            return True, 0
        key = (guild_id, user_id)
        now = time.monotonic()
        previous = self.cooldowns.get(key, 0.0)
        remaining = int(settings.cooldown_seconds - (now - previous))
        if remaining > 0:
            return False, remaining
        self.cooldowns[key] = now
        return True, 0

    async def register_guild_commands(self, guild: discord.Guild):
        settings = await self.settings(guild.id)
        guild_object = discord.Object(id=guild.id)

        for command in self.dynamic_commands.pop(guild.id, []):
            self.bot.tree.remove_command(command.name, guild=guild_object)

        commands: list[app_commands.Command] = []

        if settings.slash_verify_enabled and _SLASH_NAME_RE.fullmatch(settings.slash_verify_name):
            async def verify_callback(
                interaction: discord.Interaction,
                alliance: str,
                nickname: str,
            ):
                if not interaction.guild or not isinstance(interaction.user, discord.Member):
                    await interaction.response.send_message("Guild only.", ephemeral=True)
                    return
                await interaction.response.defer(ephemeral=True)
                result = await self.apply_profile(
                    member=interaction.user,
                    alliance=alliance,
                    nickname=nickname,
                    action="verify",
                    actor_user_id=interaction.user.id,
                )
                await interaction.followup.send(result.message, ephemeral=True)

            command = app_commands.Command(
                name=settings.slash_verify_name,
                description="Verify yourself on this server",
                callback=verify_callback,
            )
            self.bot.tree.add_command(command, guild=guild_object, override=True)
            commands.append(command)

        if settings.slash_rename_enabled and _SLASH_NAME_RE.fullmatch(settings.slash_rename_name):
            async def rename_callback(
                interaction: discord.Interaction,
                alliance: str,
                nickname: str,
            ):
                if not interaction.guild or not isinstance(interaction.user, discord.Member):
                    await interaction.response.send_message("Guild only.", ephemeral=True)
                    return
                await interaction.response.defer(ephemeral=True)
                result = await self.apply_profile(
                    member=interaction.user,
                    alliance=alliance,
                    nickname=nickname,
                    action="rename",
                    actor_user_id=interaction.user.id,
                )
                await interaction.followup.send(result.message, ephemeral=True)

            command = app_commands.Command(
                name=settings.slash_rename_name,
                description="Change your alliance and nickname",
                callback=rename_callback,
            )
            self.bot.tree.add_command(command, guild=guild_object, override=True)
            commands.append(command)

        self.dynamic_commands[guild.id] = commands
        await self.bot.tree.sync(guild=guild_object)

    async def publish_verification_message(self, guild: discord.Guild) -> discord.Message:
        settings = await self.settings(guild.id)
        if not settings.verification_channel_id:
            raise ValueError("Verification channel is not configured")
        channel = guild.get_channel(settings.verification_channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise ValueError("Configured verification channel was not found")
        view = VerificationView(self, guild.id, settings.verification_button_text)
        return await channel.send(settings.verification_message, view=view)

    async def apply_profile(
        self,
        *,
        member: discord.Member,
        alliance: str,
        nickname: str,
        action: str,
        actor_user_id: int | None,
    ) -> Result:
        guild = member.guild

        async with SessionLocal() as session:
            settings = await get_or_create_settings(session, guild.id)

            if not settings.enabled:
                return Result(False, "Verification plugin is disabled.")

            if action == "verify":
                existing = await session.get(
                    VerifiedMember, {"guild_id": guild.id, "user_id": member.id}
                )
                if existing and not settings.allow_reverification:
                    return Result(False, "You are already verified.")

            allowed, remaining = self.cooldown_ok(settings, guild.id, member.id)
            if not allowed:
                return Result(False, f"Please wait {remaining} seconds.")

            try:
                alliance, nickname, rendered = render_nickname(settings, alliance, nickname)
            except ValueError as exc:
                return Result(False, str(exc))

            old_member = await session.get(
                VerifiedMember, {"guild_id": guild.id, "user_id": member.id}
            )
            old_alliance = old_member.alliance if old_member else None
            old_nickname = old_member.nickname if old_member else None
            old_rendered = old_member.rendered_nickname if old_member else member.display_name

            role_assigned = False
            role_error = None
            nickname_error = None

            try:
                await member.edit(nick=rendered, reason=f"{PLUGIN_ID}:{action}")
            except discord.Forbidden:
                nickname_error = "Bot cannot change this member's nickname. Check role hierarchy."
            except discord.HTTPException as exc:
                nickname_error = f"Discord rejected the nickname change: {exc}"

            should_assign = (
                action == "verify" and settings.assign_role_on_verify
            ) or (
                action == "rename" and settings.assign_role_on_rename
            )

            if should_assign and settings.verified_role_id:
                role = guild.get_role(settings.verified_role_id)
                if role:
                    if role in member.roles:
                        role_assigned = True
                    else:
                        try:
                            await member.add_roles(role, reason=f"{PLUGIN_ID}:{action}")
                            role_assigned = True
                        except discord.Forbidden:
                            role_error = "Bot cannot assign the configured role. Check role hierarchy."
                        except discord.HTTPException as exc:
                            role_error = f"Discord rejected role assignment: {exc}"
                else:
                    role_error = "Configured role was not found."

            await upsert_member(
                session,
                guild_id=guild.id,
                user_id=member.id,
                discord_name=str(member),
                alliance=alliance,
                nickname=nickname,
                rendered_nickname=rendered,
                verified_by="self",
            )

            await add_audit(
                session,
                guild_id=guild.id,
                user_id=member.id,
                actor_user_id=actor_user_id,
                action=action,
                old_alliance=old_alliance,
                new_alliance=alliance,
                old_nickname=old_nickname,
                new_nickname=nickname,
                old_rendered_nickname=old_rendered,
                new_rendered_nickname=rendered,
                role_id=settings.verified_role_id,
                role_assigned=role_assigned,
                details={
                    "nickname_error": nickname_error,
                    "role_error": role_error,
                },
            )
            await session.commit()

        await self.send_success_message(member, settings, alliance, nickname, rendered)
        await self.send_log(member, settings, action, alliance, nickname, rendered, role_assigned, nickname_error, role_error)

        errors = [x for x in (nickname_error, role_error) if x]
        if errors:
            return Result(
                False,
                "Profile saved, but Discord action was partially completed:\n" + "\n".join(errors),
                rendered,
                role_assigned,
            )
        return Result(True, f"✅ Success. Your nickname is now **{rendered}**.", rendered, role_assigned)

    async def send_success_message(
        self,
        member: discord.Member,
        settings: VerificationSettings,
        alliance: str,
        nickname: str,
        rendered: str,
    ):
        if not settings.success_message_enabled or not settings.verification_channel_id:
            return

        channel = member.guild.get_channel(settings.verification_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        role = member.guild.get_role(settings.verified_role_id) if settings.verified_role_id else None
        replacements = {
            "{MENTION}": member.mention,
            "{USERNAME}": member.name,
            "{DISPLAY_NAME}": member.display_name,
            "{NICKNAME}": nickname,
            "{ALLIANCE}": alliance,
            "{ROLE}": role.mention if role else "",
            "{SERVER}": member.guild.name,
            "{RENDERED_NICKNAME}": rendered,
        }
        text = settings.success_message_text
        for token, value in replacements.items():
            text = text.replace(token, value)

        delete_after = settings.success_message_delete_after or None
        await channel.send(
            text[:2000],
            delete_after=delete_after,
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )

    async def send_log(
        self,
        member: discord.Member,
        settings: VerificationSettings,
        action: str,
        alliance: str,
        nickname: str,
        rendered: str,
        role_assigned: bool,
        nickname_error: str | None,
        role_error: str | None,
    ):
        if not settings.log_channel_id:
            return
        channel = member.guild.get_channel(settings.log_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        status = "success" if not nickname_error and not role_error else "partial"
        embed = discord.Embed(
            title=f"Verification Level 1: {action}",
            description=f"Status: **{status}**",
        )
        embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="Alliance", value=alliance, inline=True)
        embed.add_field(name="Nickname", value=nickname, inline=True)
        embed.add_field(name="Result", value=rendered, inline=False)
        embed.add_field(name="Role assigned", value=str(role_assigned), inline=True)
        if nickname_error:
            embed.add_field(name="Nickname error", value=nickname_error, inline=False)
        if role_error:
            embed.add_field(name="Role error", value=role_error, inline=False)
        await channel.send(embed=embed)

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or not isinstance(message.author, discord.Member):
            return

        settings = await self.settings(message.guild.id)
        if not settings.enabled or not self.channel_allowed(settings, message.channel.id):
            return

        verify_prefix = f"{settings.command_prefix}{settings.prefix_verify_name}"
        rename_prefix = f"{settings.command_prefix}{settings.prefix_rename_name}"

        action = None
        command_prefix = None
        if settings.prefix_verify_enabled and (
            message.content == verify_prefix or message.content.startswith(verify_prefix + " ")
        ):
            action = "verify"
            command_prefix = verify_prefix
        elif settings.prefix_rename_enabled and (
            message.content == rename_prefix or message.content.startswith(rename_prefix + " ")
        ):
            action = "rename"
            command_prefix = rename_prefix

        if not action:
            return

        payload = message.content[len(command_prefix):].strip()
        parts = payload.split(maxsplit=1)
        if len(parts) != 2:
            await message.channel.send(
                f"Usage: `{command_prefix} ALLIANCE NICKNAME`",
                delete_after=30,
            )
            return

        result = await self.apply_profile(
            member=message.author,
            alliance=parts[0],
            nickname=parts[1],
            action=action,
            actor_user_id=message.author.id,
        )

        if settings.delete_user_command:
            try:
                await message.delete()
            except discord.HTTPException:
                pass

        await message.channel.send(
            result.message,
            delete_after=30,
            allowed_mentions=discord.AllowedMentions.none(),
        )


_runtime: VerificationRuntime | None = None


async def setup(bot: discord.Client, services: Any | None = None):
    global _runtime
    _runtime = VerificationRuntime(bot)
    await _runtime.start()
    return _runtime


async def teardown(bot: discord.Client):
    global _runtime
    if _runtime:
        await _runtime.stop()
        _runtime = None


def get_runtime() -> VerificationRuntime | None:
    return _runtime
