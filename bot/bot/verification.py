import discord
import httpx

from bot.config import settings


class VerificationClient:
    def __init__(self, bot: discord.Client) -> None:
        self.bot = bot
        self.base_url = settings.backend_url.rstrip("/")
        self.headers = {
            "X-ShieldNet-Service-Token":
                settings.internal_service_token,
        }

    async def create_request(
        self,
        *,
        guild_id: int,
        discord_user_id: int,
        alliance: str,
        nickname: str,
        server_number: str,
    ) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/"
                f"verification/guilds/{guild_id}/requests",
                headers=self.headers,
                json={
                    "discord_user_id": discord_user_id,
                    "alliance": alliance,
                    "nickname": nickname,
                    "server_number": server_number,
                },
            )

        response.raise_for_status()
        return response.json()

    async def settings(self, guild_id: int) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/internal/verification/guilds/{guild_id}/settings",
                headers=self.headers,
            )
        response.raise_for_status()
        return response.json()

    async def fetch_pending(
        self,
        guild_id: int,
    ) -> list[dict]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/internal/"
                f"verification/guilds/{guild_id}/"
                "requests/pending",
                headers=self.headers,
            )

        response.raise_for_status()
        return response.json().get("items", [])

    async def fetch_review_notifications(self, guild_id: int) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/internal/verification/"
                f"guilds/{guild_id}/review-notifications",
                headers=self.headers,
            )
        response.raise_for_status()
        return response.json()

    async def report_review_notification(
        self,
        request_id: str,
        status: str,
        message: str | None,
    ) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/verification/"
                f"review-notifications/{request_id}/result",
                headers=self.headers,
                json={"status": status, "result_message": message},
            )
        response.raise_for_status()

    async def latest_request(
        self,
        guild_id: int,
        discord_user_id: int,
    ) -> dict | None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/internal/verification/"
                f"guilds/{guild_id}/users/{discord_user_id}/latest",
                headers=self.headers,
            )
        response.raise_for_status()
        return response.json().get("request")

    async def discord_approve(self, request_id: str, moderator_id: int) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/verification/"
                f"requests/{request_id}/discord-approve",
                headers=self.headers,
                json={"moderator_discord_user_id": moderator_id, "reason": None},
            )
        response.raise_for_status()

    async def discord_reject(
        self,
        request_id: str,
        moderator_id: int,
        reason: str,
    ) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/verification/"
                f"requests/{request_id}/discord-reject",
                headers=self.headers,
                json={"moderator_discord_user_id": moderator_id, "reason": reason},
            )
        response.raise_for_status()

    async def fetch_notifications(
        self,
        guild_id: int,
    ) -> list[dict]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/internal/"
                f"verification/guilds/{guild_id}/notifications",
                headers=self.headers,
            )
        response.raise_for_status()
        return response.json().get("items", [])

    async def report_notification(
        self,
        request_id: str,
        status: str,
        message: str | None,
    ) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/"
                f"verification/notifications/{request_id}/result",
                headers=self.headers,
                json={
                    "status": status,
                    "result_message": message,
                },
            )
        response.raise_for_status()

    async def report(
        self,
        request_id: str,
        status: str,
        message: str,
    ) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/internal/"
                f"verification/requests/{request_id}/result",
                headers=self.headers,
                json={
                    "status": status,
                    "result_message": message,
                },
            )

        response.raise_for_status()

    async def process(
        self,
        guild: discord.Guild,
        item: dict,
    ) -> None:
        request_id = str(item["id"])
        user_id = int(item["discord_user_id"])
        requested_nickname = str(
            item["requested_nickname"]
        )
        verified_role_id = item.get(
            "verified_role_id"
        )

        try:
            member = guild.get_member(user_id)

            if member is None:
                member = await guild.fetch_member(user_id)

            await member.edit(
                nick=requested_nickname,
                reason="GuildConsole verification approved",
            )

            messages = ["Nickname updated."]

            if verified_role_id:
                role = guild.get_role(
                    int(verified_role_id)
                )

                if role is None:
                    raise RuntimeError(
                        "Configured Verified role was not found."
                    )

                await member.add_roles(
                    role,
                    reason="GuildConsole verification approved",
                )
                messages.append(
                    f"Role {role.name} assigned."
                )

            await self.report(
                request_id,
                "completed",
                " ".join(messages),
            )

            try:
                await member.send(
                    f"Your verification on **{guild.name}** "
                    "was approved.\n"
                    f"Your nickname is now "
                    f"**{requested_nickname}**."
                )
            except discord.HTTPException:
                pass

        except Exception as exc:
            await self.report(
                request_id,
                "failed",
                str(exc)[:2000],
            )

            try:
                user = self.bot.get_user(user_id)
                if user is None:
                    user = await self.bot.fetch_user(user_id)

                await user.send(
                    f"Verification on **{guild.name}** "
                    "could not be completed.\n"
                    f"Reason: {str(exc)[:500]}"
                )
            except discord.HTTPException:
                pass


    async def process_notification(
        self,
        guild: discord.Guild,
        item: dict,
    ) -> None:
        request_id = str(item["id"])
        user_id = int(item["discord_user_id"])
        reason = str(
            item.get("message")
            or "The request was rejected."
        )

        try:
            user = self.bot.get_user(user_id)
            if user is None:
                user = await self.bot.fetch_user(user_id)

            await user.send(
                f"Your verification on **{guild.name}** "
                f"was rejected.\nReason: {reason}"
            )

            await self.report_notification(
                request_id,
                "completed",
                "DM sent.",
            )
        except Exception as exc:
            await self.report_notification(
                request_id,
                "failed",
                str(exc)[:2000],
            )

    async def process_review_notification(
        self,
        guild: discord.Guild,
        channel_id: int,
        item: dict,
    ) -> None:
        channel = guild.get_channel(channel_id)

        if channel is None:
            channel = await guild.fetch_channel(channel_id)

        embed = discord.Embed(
            title="New verification request",
            description=f"Requested nickname: **{item['requested_nickname']}**",
        )
        embed.add_field(name="Alliance", value=str(item["alliance"]))
        embed.add_field(name="Nickname", value=str(item["nickname"]))
        embed.add_field(name="Server", value=str(item.get("server_number") or "—"))
        embed.add_field(
            name="Discord user",
            value=f"<@{item['discord_user_id']}>",
            inline=False,
        )
        embed.set_footer(text=f"Request ID: {item['id']}")

        view = VerificationReviewView(self)

        await channel.send(embed=embed, view=view)


class VerificationRejectModal(discord.ui.Modal, title="Reject verification"):
    reason = discord.ui.TextInput(
        label="Reason",
        style=discord.TextStyle.paragraph,
        min_length=1,
        max_length=1000,
    )

    def __init__(self, client: VerificationClient, request_id: str) -> None:
        super().__init__()
        self.client = client
        self.request_id = request_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await self.client.discord_reject(
            self.request_id,
            interaction.user.id,
            str(self.reason.value),
        )
        await interaction.followup.send("Request rejected.", ephemeral=True)

        if interaction.message:
            await interaction.message.edit(view=None)


class VerificationReviewView(discord.ui.View):
    def __init__(self, client: VerificationClient) -> None:
        super().__init__(timeout=None)
        self.client = client

    @staticmethod
    def request_id(interaction: discord.Interaction) -> str | None:
        if not interaction.message or not interaction.message.embeds:
            return None

        footer = interaction.message.embeds[0].footer.text or ""
        prefix = "Request ID: "
        return footer[len(prefix):].strip() if footer.startswith(prefix) else None

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="shieldnet:verification:approve",
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button

        request_id = self.request_id(interaction)

        if not request_id:
            await interaction.response.send_message(
                "Request ID not found.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        await self.client.discord_approve(request_id, interaction.user.id)
        await interaction.followup.send("Request approved.", ephemeral=True)

        if interaction.message:
            await interaction.message.edit(view=None)

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        custom_id="shieldnet:verification:reject",
    )
    async def reject(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        request_id = self.request_id(interaction)

        if not request_id:
            await interaction.response.send_message(
                "Request ID not found.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            VerificationRejectModal(self.client, request_id)
        )


class VerifyModal(
    discord.ui.Modal,
    title="GuildConsole Verification",
):
    alliance = discord.ui.TextInput(
        label="Alliance",
        placeholder="EVEX",
        min_length=1,
        max_length=32,
    )

    nickname = discord.ui.TextInput(
        label="Nickname",
        placeholder="Mr.Cat",
        min_length=1,
        max_length=64,
    )

    server_number = discord.ui.TextInput(
        label="Server number",
        placeholder="2279",
        min_length=1,
        max_length=32,
    )

    def __init__(
        self,
        verification_client: VerificationClient,
    ) -> None:
        super().__init__()
        self.verification_client = verification_client

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command is available only on a server.",
                ephemeral=True,
            )
            return

        config = await self.verification_client.settings(interaction.guild.id)
        channel_id = config.get("invocation_channel_id")
        if not config.get("enabled") or (channel_id and str(interaction.channel_id) != channel_id):
            await interaction.response.send_message(
                f"Use verification in <#{channel_id}>." if channel_id else "Verification is unavailable.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        try:
            item = (
                await self.verification_client.create_request(
                    guild_id=interaction.guild.id,
                    discord_user_id=interaction.user.id,
                    alliance=str(self.alliance.value),
                    nickname=str(self.nickname.value),
                    server_number=str(self.server_number.value),
                )
            )

            status = item.get("status")

            if status == "approved":
                message = (
                    "Verification request created and "
                    "automatically approved.\n"
                    "GuildConsole will apply it shortly."
                )
            else:
                message = (
                    "Verification request created.\n"
                    "It is waiting for administrator approval."
                )

            await interaction.followup.send(
                message
                + "\nRequested nickname: "
                + f"**{item['requested_nickname']}**.",
                ephemeral=True,
            )
        except httpx.HTTPStatusError as exc:
            detail = (
                "Unable to create verification request."
            )

            try:
                payload = exc.response.json()
                detail = str(
                    payload.get("detail") or detail
                )
            except Exception:
                pass

            await interaction.followup.send(
                detail,
                ephemeral=True,
            )

        except Exception:
            await interaction.followup.send(
                "Unexpected verification error.",
                ephemeral=True,
            )


class VerificationStartView(discord.ui.View):
    def __init__(self, verification_client: VerificationClient) -> None:
        super().__init__(timeout=300)
        self.verification_client = verification_client

    @discord.ui.button(label="Start verification", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(VerifyModal(self.verification_client))
