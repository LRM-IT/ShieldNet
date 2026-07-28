from bot.verification import VerificationClient, VerifyModal, VerificationReviewView
from bot.permissions import PermissionClient
import asyncio
import logging
from datetime import UTC, datetime

import discord
import json
import socket
from redis.asyncio import Redis
from discord import app_commands
from discord.ext import tasks

from bot.backend import BackendAPIError, BackendClient
from bot.config import settings
from bot.config_cache import GuildConfigCache, GuildModuleState
from bot.members_sync import MemberSyncClient
from bot.member_actions import MemberActionWorker
from bot.guild_roles_sync import GuildRoleSyncClient
from bot.security_sync import SecuritySyncClient
from bot.explorer_sync import ExplorerSyncClient
from bot.automation_runtime import AutomationRuntimeClient
from bot.leadership import LeadershipSyncClient
from bot.discord_management import DiscordManagementWorker
from bot.guild_dm_broadcast import GuildDMBroadcastWorker

logger = logging.getLogger(__name__)


class ShieldNetBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.presences = True
        intents.voice_states = True
        super().__init__(intents=intents, chunk_guilds_at_startup=False)

        self.tree = app_commands.CommandTree(self)
        self.backend = BackendClient()
        self.verification = VerificationClient(self)
        self.permissions = PermissionClient()
        self.cache = GuildConfigCache()
        self.member_sync = MemberSyncClient()
        self.member_actions = MemberActionWorker(self)
        self.guild_role_sync = GuildRoleSyncClient(self)
        self.security_sync = SecuritySyncClient()
        self.explorer_sync = ExplorerSyncClient()
        self.automation_runtime = AutomationRuntimeClient(self)
        self.leadership_sync = LeadershipSyncClient(self)
        self.discord_management = DiscordManagementWorker(self)
        self.guild_dm_broadcast = GuildDMBroadcastWorker(self)
        self._initial_sync_done = False
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self.worker_name = f"discord-worker:{socket.gethostname()}"
        self._register_commands()

    def _register_commands(self) -> None:
        @self.tree.command(name="shieldnet_status", description="Show ShieldNet status.")
        async def status(interaction: discord.Interaction) -> None:
            if interaction.guild is None:
                await interaction.response.send_message("Server only.", ephemeral=True)
                return
            state = self.cache.get(interaction.guild.id)
            revision = state.configuration_revision if state else 0
            await interaction.response.send_message(
                f"ShieldNet online. Revision: {revision}",
                ephemeral=True,
            )

        @self.tree.command(name="shieldnet_modules", description="Show enabled modules.")
        async def modules(interaction: discord.Interaction) -> None:
            if interaction.guild is None:
                await interaction.response.send_message("Server only.", ephemeral=True)
                return
            state = await self.ensure_config(interaction.guild.id)
            enabled = [
                item.get("name", key)
                for key, item in state.modules.items()
                if item.get("enabled")
            ]
            await interaction.response.send_message(
                "Enabled modules:\n" + (
                    "\n".join(f"• {name}" for name in enabled)
                    if enabled else "None"
                ),
                ephemeral=True,
            )

        @self.tree.command(name="shieldnet_reload", description="Reload ShieldNet settings.")
        @app_commands.default_permissions(manage_guild=True)
        async def reload_cmd(interaction: discord.Interaction) -> None:
            if not await self._can_manage(interaction):
                return
            await interaction.response.defer(ephemeral=True)
            state = await self.reload_config(interaction.guild.id)
            await interaction.followup.send(
                f"Configuration reloaded. Revision: {state.configuration_revision}",
                ephemeral=True,
            )

        @self.tree.command(name="shieldnet_clear_cache", description="Clear ShieldNet cache.")
        @app_commands.default_permissions(manage_guild=True)
        async def clear_cmd(interaction: discord.Interaction) -> None:
            if not await self._can_manage(interaction):
                return
            await interaction.response.defer(ephemeral=True)
            self.cache.clear(interaction.guild.id)
            state = await self.reload_config(interaction.guild.id)
            await interaction.followup.send(
                f"Cache cleared. Revision: {state.configuration_revision}",
                ephemeral=True,
            )

        @self.tree.command(
            name="verify",
            description="Verify your alliance and nickname.",
        )
        async def verify(
            interaction: discord.Interaction,
        ) -> None:
            await interaction.response.send_modal(
                VerifyModal(self.verification)
            )


        @self.tree.command(
            name="verify_status",
            description="Show your latest verification request.",
        )
        async def verify_status(interaction: discord.Interaction) -> None:
            if interaction.guild is None:
                await interaction.response.send_message(
                    "Server only.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)
            item = await self.verification.latest_request(
                interaction.guild.id,
                interaction.user.id,
            )

            if item is None:
                await interaction.followup.send(
                    "You do not have verification requests.",
                    ephemeral=True,
                )
                return

            message = (
                f"Status: **{item['status']}**\n"
                f"Requested nickname: **{item['requested_nickname']}**"
            )
            reason = item.get("decision_reason") or item.get("result_message")

            if reason:
                message += f"\nMessage: {reason}"

            await interaction.followup.send(message, ephemeral=True)

        @self.tree.command(
            name="translate",
            description="Translate text using this server's configured AI provider.",
        )
        @app_commands.describe(
            text="Text to translate",
            target_language="Target language code, for example: en, uk, de",
            source_language="Source language code or auto",
            private="Show the result only to you",
        )
        async def translate(
            interaction: discord.Interaction,
            text: app_commands.Range[str, 1, 4000],
            target_language: app_commands.Range[str, 2, 32],
            source_language: app_commands.Range[str, 2, 32] = "auto",
            private: bool = True,
        ) -> None:
            if interaction.guild is None:
                await interaction.response.send_message("Server only.", ephemeral=True)
                return

            target = target_language.strip().lower()
            source = source_language.strip().lower() or "auto"
            await interaction.response.defer(ephemeral=private, thinking=True)

            try:
                result = await self.backend.execute_ai(
                    guild_id=interaction.guild.id,
                    module_key="translator",
                    capability="translation",
                    input_text=str(text),
                    source_language=source,
                    target_language=target,
                    metadata={
                        "source": "discord_slash_command",
                        "discord_user_id": interaction.user.id,
                        "discord_channel_id": interaction.channel_id,
                        "discord_interaction_id": interaction.id,
                    },
                )
            except BackendAPIError as exc:
                logger.warning(
                    "Translation failed: guild=%s user=%s status=%s error=%s",
                    interaction.guild.id, interaction.user.id, exc.status_code, exc,
                )
                message = str(exc)
                if exc.status_code == 404:
                    message = (
                        "No AI provider is configured for the Translator module on this server. "
                        "Configure translator/translation in ShieldNet AI & Integrations."
                    )
                await interaction.followup.send(f"Translation failed: {message}", ephemeral=True)
                return
            except Exception:
                logger.exception(
                    "Unexpected translation failure: guild=%s user=%s",
                    interaction.guild.id, interaction.user.id,
                )
                await interaction.followup.send(
                    "Translation failed because of an unexpected internal error.",
                    ephemeral=True,
                )
                return

            translated = str(result.get("text") or "").strip()
            if not translated:
                await interaction.followup.send(
                    "The configured provider returned an empty translation.",
                    ephemeral=True,
                )
                return

            provider = result.get("provider_name") or result.get("provider_type") or "AI provider"
            model = result.get("model")
            latency = result.get("latency_ms")
            details = f"Provider: {provider}"
            if model:
                details += f" · Model: {model}"
            if isinstance(latency, int):
                details += f" · {latency} ms"

            chunks = [translated[i:i + 1900] for i in range(0, len(translated), 1900)]
            await interaction.followup.send(
                f"{chunks[0]}\n\n-# {details}",
                ephemeral=private,
            )
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk, ephemeral=private)

    async def setup_hook(self) -> None:
        self.add_view(VerificationReviewView(self.verification))
        if settings.sync_commands_on_start:
            synced = await self.tree.sync()
            logger.info("Commands synchronized: %s", len(synced))
        self.periodic_sync.start()
        self.verification_loop.start()
        self.verification_notification_loop.start()
        self.verification_review_loop.start()
        self.leadership_sync_loop.start()
        self.discord_management_loop.start()
        self.guild_dm_broadcast_loop.start()
        self.member_action_loop.start()
        self.security_snapshot_loop.start()
        self.explorer_snapshot_loop.start()
        self.runtime_heartbeat_loop.start()
        asyncio.create_task(self.queue_worker())

    async def close(self) -> None:
        if self.periodic_sync.is_running():
            self.periodic_sync.cancel()
        await self.redis.aclose()
        await super().close()

    async def on_ready(self) -> None:
        logger.info("Connected as %s; guilds=%s", self.user, len(self.guilds))
        if not self._initial_sync_done:
            self._initial_sync_done = True
            asyncio.create_task(self._sync_all())
            asyncio.create_task(self._sync_all_guild_roles())

    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self.backend.register_guild(guild)
        await self.reload_config(guild.id)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self.cache.clear(guild.id)
        await self.backend.mark_guild_left(guild.id)

    async def ensure_config(self, guild_id: int) -> GuildModuleState:
        state = self.cache.get(guild_id)
        return state if state else await self.reload_config(guild_id)

    async def reload_config(self, guild_id: int) -> GuildModuleState:
        async with self.cache.lock(guild_id):
            payload = await self.backend.get_guild_modules(guild_id)
            modules = {
                str(item["module_key"]): item
                for item in payload.get("modules", [])
                if isinstance(item, dict) and item.get("module_key")
            }
            state = GuildModuleState(
                guild_id=guild_id,
                configuration_revision=int(payload.get("configuration_revision", 0)),
                modules=modules,
                loaded_at=datetime.now(UTC),
            )
            self.cache.set(state)
            logger.info(
                "Configuration loaded: guild=%s revision=%s modules=%s",
                guild_id,
                state.configuration_revision,
                len(modules),
            )
            return state

    async def _sync_all(self) -> None:
        for guild in self.guilds:
            try:
                await self.backend.register_guild(guild)
                await self.reload_config(guild.id)
            except Exception:
                logger.exception("Initial sync failed for guild %s", guild.id)
            await asyncio.sleep(.25)

    @tasks.loop(minutes=5)
    async def periodic_sync(self) -> None:
        for guild in self.guilds:
            try:
                await self.reload_config(guild.id)
            except Exception:
                logger.exception("Periodic sync failed for guild %s", guild.id)

    @periodic_sync.before_loop
    async def before_periodic_sync(self) -> None:
        await self.wait_until_ready()

    @staticmethod
    async def _can_manage(interaction: discord.Interaction) -> bool:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Server only.", ephemeral=True)
            return False
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "Manage Server permission is required.",
                ephemeral=True,
            )
            return False
        return True

    async def on_member_join(self, member: discord.Member) -> None:
        try:
            await self.member_sync.sync_member(member)
            await self.automation_runtime.emit(member.guild, "member.joined", f"{member.id}:{member.joined_at.isoformat() if member.joined_at else datetime.now(UTC).isoformat()}", self._member_context(member))
        except Exception:
            logger.exception("Member join sync/automation failed: %s", member.id)

    async def on_member_remove(self, member: discord.Member) -> None:
        try:
            await self.member_sync.mark_left(member.guild.id, member.id)
            await self.automation_runtime.emit(member.guild, "member.left", f"{member.id}:{datetime.now(UTC).isoformat()}", self._member_context(member))
        except Exception:
            logger.exception("Member leave sync/automation failed: %s", member.id)

    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        try:
            await self.member_sync.sync_member(after)
            before_ids = {r.id for r in before.roles}
            for role in after.roles:
                if role.id not in before_ids:
                    context = self._member_context(after)
                    context["role"] = {"id": str(role.id), "name": role.name}
                    await self.automation_runtime.emit(after.guild, "member.role_added", f"{after.id}:{role.id}:{datetime.now(UTC).isoformat()}", context)
        except Exception:
            logger.exception("Member update sync/automation failed: %s", after.id)

    @staticmethod
    def _member_context(member: discord.Member) -> dict:
        return {"member": {"id": str(member.id), "name": str(member), "display_name": member.display_name,
                "bot": member.bot, "roles": [str(r.id) for r in member.roles],
                "account_age_days": max(0, (datetime.now(UTC) - member.created_at).days),
                "joined_at": member.joined_at.isoformat() if member.joined_at else None},
                "guild": {"id": str(member.guild.id), "name": member.guild.name}}


    async def on_presence_update(self, before: discord.Member, after: discord.Member) -> None:
        try:
            await self.member_sync.sync_member(after)
        except Exception:
            logger.exception("Member presence sync failed: %s", after.id)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        try:
            await self.member_sync.sync_member(member)
        except Exception:
            logger.exception("Member voice sync failed: %s", member.id)

    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        try:
            await self.member_sync.mark_activity(message.guild.id, message.author.id)
        except Exception:
            logger.exception("Member activity sync failed: %s", message.author.id)

    @tasks.loop(seconds=10)
    async def member_action_loop(self) -> None:
        for guild in self.guilds:
            try:
                actions = await self.member_actions.fetch(guild.id)
                for action in actions:
                    await self.member_actions.execute(guild, action)
            except Exception:
                logger.exception("Member action queue failed: %s", guild.id)

    @member_action_loop.before_loop
    async def before_member_action_loop(self) -> None:
        await self.wait_until_ready()


    @tasks.loop(minutes=15)
    async def security_snapshot_loop(self) -> None:
        for guild in self.guilds:
            try:
                await self.security_sync.synchronize(guild)
            except Exception:
                logger.exception("Security snapshot failed: %s", guild.id)

    @security_snapshot_loop.before_loop
    async def before_security_snapshot_loop(self) -> None:
        await self.wait_until_ready()
        await asyncio.sleep(15)


    @tasks.loop(minutes=10)
    async def explorer_snapshot_loop(self) -> None:
        for guild in self.guilds:
            try:
                await self.explorer_sync.synchronize(guild)
            except Exception:
                logger.exception("Explorer snapshot failed: %s", guild.id)

    @explorer_snapshot_loop.before_loop
    async def before_explorer_snapshot_loop(self) -> None:
        await self.wait_until_ready()
        await asyncio.sleep(20)

    @tasks.loop(seconds=30)
    async def runtime_heartbeat_loop(self) -> None:
        try:
            await self.backend.heartbeat(
                worker_name=self.worker_name,
                worker_type="discord_worker",
                status="online",
                metadata={"guilds": len(self.guilds), "latency_ms": round(self.latency * 1000, 2)},
            )
        except Exception:
            logger.exception("Runtime heartbeat failed")

    @runtime_heartbeat_loop.before_loop
    async def before_runtime_heartbeat_loop(self) -> None:
        await self.wait_until_ready()

    async def queue_worker(self) -> None:
        await self.wait_until_ready()
        logger.info("Redis queue worker started: %s", settings.worker_queue)
        while not self.is_closed():
            try:
                item = await self.redis.brpop(settings.worker_queue, timeout=10)
                if not item:
                    continue
                _, raw = item
                payload = json.loads(raw)
                job = str(payload.get("job") or "")
                guild_id = payload.get("guild_id")
                guilds = [self.get_guild(int(guild_id))] if guild_id else list(self.guilds)
                guilds = [g for g in guilds if g is not None]
                logger.info("Queue job received: job=%s guilds=%s", job, len(guilds))
                if job == "sync_guilds":
                    for guild in guilds:
                        await self.backend.register_guild(guild)
                        await self.reload_config(guild.id)
                elif job == "sync_roles":
                    for guild in guilds:
                        await self.guild_role_sync.synchronize(guild)
                elif job == "sync_explorer":
                    for guild in guilds:
                        await self.explorer_sync.synchronize(guild)
                elif job == "security_scan":
                    for guild in guilds:
                        await self.security_sync.synchronize(guild)
                elif job == "sync_members":
                    for guild in guilds:
                        await guild.chunk(cache=True)
                        for member in guild.members:
                            await self.member_sync.sync_member(member)
                elif job == "automation_execute":
                    automation = payload.get("automation") or {}
                    for guild in guilds:
                        await self.automation_runtime.execute(guild, automation)
                else:
                    logger.warning("Unsupported queue job: %s", job)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Redis queue job failed")
                await asyncio.sleep(2)

    async def on_guild_role_create(self, role: discord.Role) -> None:
        try:
            await self.guild_role_sync.synchronize(role.guild)
        except Exception:
            logger.exception(
                "Guild role create sync failed: %s",
                role.id,
            )

    async def on_guild_role_update(
        self,
        before: discord.Role,
        after: discord.Role,
    ) -> None:
        try:
            await self.guild_role_sync.synchronize(after.guild)
        except Exception:
            logger.exception(
                "Guild role update sync failed: %s",
                after.id,
            )

    async def on_guild_role_delete(self, role: discord.Role) -> None:
        try:
            await self.guild_role_sync.synchronize(role.guild)
        except Exception:
            logger.exception(
                "Guild role delete sync failed: %s",
                role.id,
            )

    async def _sync_all_guild_roles(self) -> None:
        for guild in self.guilds:
            try:
                await self.guild_role_sync.synchronize(guild)
                logger.info(
                    "Guild roles synchronized: guild=%s roles=%s",
                    guild.id,
                    len(guild.roles),
                )
            except Exception:
                logger.exception(
                    "Initial guild role synchronization failed: %s",
                    guild.id,
                )

            await asyncio.sleep(0.25)

    @tasks.loop(seconds=12)
    async def leadership_sync_loop(self) -> None:
        try:
            items = await self.leadership_sync.fetch_pending()
            for item in items:
                try:
                    await self.leadership_sync.process(item)
                    await self.leadership_sync.report(str(item["application_id"]), "completed", "Leadership and language roles synchronized.")
                except Exception as exc:
                    await self.leadership_sync.report(str(item["application_id"]), "failed", str(exc)[:2000])
        except Exception:
            logger.exception("Leadership role synchronization queue failed")

    @leadership_sync_loop.before_loop
    async def before_leadership_sync_loop(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(seconds=10)
    async def verification_loop(self) -> None:
        for guild in self.guilds:
            try:
                items = await self.verification.fetch_pending(guild.id)
                for item in items:
                    await self.verification.process(guild, item)
            except Exception:
                logger.exception("Verification queue failed: %s", guild.id)

    @verification_loop.before_loop
    async def before_verification_loop(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(seconds=10)
    async def verification_notification_loop(self) -> None:
        for guild in self.guilds:
            try:
                items = await self.verification.fetch_notifications(
                    guild.id
                )
                for item in items:
                    await self.verification.process_notification(
                        guild,
                        item,
                    )
            except Exception:
                logger.exception(
                    "Verification notification queue failed: %s",
                    guild.id,
                )

    @verification_notification_loop.before_loop
    async def before_verification_notification_loop(self) -> None:
        await self.wait_until_ready()


    @tasks.loop(seconds=15)
    async def discord_management_loop(self) -> None:
        try:
            await self.discord_management.run_once()
        except Exception:
            logger.exception("Discord management loop failed")

    @discord_management_loop.before_loop
    async def before_discord_management_loop(self) -> None:
        await self.wait_until_ready()


    @tasks.loop(seconds=5)
    async def guild_dm_broadcast_loop(self) -> None:
        try:
            await self.guild_dm_broadcast.run_once()
        except Exception:
            logger.exception("Guild DM Broadcast queue failed")

    @guild_dm_broadcast_loop.before_loop
    async def before_guild_dm_broadcast_loop(self) -> None:
        await self.wait_until_ready()


    @tasks.loop(seconds=10)
    async def verification_review_loop(self) -> None:
        for guild in self.guilds:
            try:
                payload = await self.verification.fetch_review_notifications(
                    guild.id
                )
                channel_id = payload.get("channel_id")

                if not channel_id:
                    continue

                for item in payload.get("items", []):
                    try:
                        await self.verification.process_review_notification(
                            guild,
                            int(channel_id),
                            item,
                        )
                        await self.verification.report_review_notification(
                            str(item["id"]),
                            "completed",
                            "Review notification sent.",
                        )
                    except Exception as exc:
                        await self.verification.report_review_notification(
                            str(item["id"]),
                            "failed",
                            str(exc)[:2000],
                        )

            except Exception:
                logger.exception(
                    "Verification review queue failed: %s",
                    guild.id,
                )

    @verification_review_loop.before_loop
    async def before_verification_review_loop(self) -> None:
        await self.wait_until_ready()
