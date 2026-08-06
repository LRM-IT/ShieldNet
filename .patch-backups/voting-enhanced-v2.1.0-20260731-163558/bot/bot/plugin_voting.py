from __future__ import annotations
import logging
from uuid import UUID

import discord
import httpx
from discord.ext import tasks

from bot.config import settings

log = logging.getLogger(__name__)


class VoteButton(discord.ui.Button):
    def __init__(self, worker, poll_id: str, option_id: str, label: str, row: int):
        super().__init__(label=label[:80], style=discord.ButtonStyle.secondary, row=row)
        self.worker = worker
        self.poll_id = poll_id
        self.option_id = option_id
        self.custom_id = f"sn_vote:{poll_id}:{option_id}"

    async def callback(self, interaction: discord.Interaction):
        try:
            result = await self.worker.submit_vote(
                self.poll_id, self.option_id, interaction.user.id,
                interaction.locale.value if interaction.locale else None,
            )
            await interaction.response.send_message(
                result.get("message", "Vote recorded."), ephemeral=True
            )
        except Exception as exc:
            log.exception("Voting failed")
            await interaction.response.send_message(
                f"Unable to record vote: {str(exc)[:180]}", ephemeral=True
            )


class VotingView(discord.ui.View):
    def __init__(self, worker, poll: dict, language: str):
        super().__init__(timeout=None)
        for index, option in enumerate(poll.get("options", [])):
            translation = option.get("translations", {}).get(language) or \
                          option.get("translations", {}).get(poll["primary_language"]) or {}
            self.add_item(VoteButton(
                worker, poll["id"], option["id"],
                f'{option.get("emoji") or ""} {translation.get("label") or "Option"}'.strip(),
                index // 5
            ))


class VotingWorker:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.base = settings.backend_url.rstrip("/")
        self.headers = {"X-ShieldNet-Service-Token": settings.internal_service_token}

    async def submit_vote(self, poll_id, option_id, user_id, language):
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base}/api/v1/internal/discord/plugins/voting/{poll_id}/vote",
                headers=self.headers,
                json={"option_id": option_id, "discord_user_id": user_id,
                      "language_code": language},
            )
            response.raise_for_status()
            return response.json()

    @tasks.loop(seconds=5)
    async def loop(self):
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base}/api/v1/internal/discord/plugins/voting/jobs",
                headers=self.headers,
            )
            response.raise_for_status()
            for job in response.json().get("items", []):
                try:
                    await self.process(job)
                except Exception as exc:
                    log.exception("Voting job failed: %s", job.get("id"))
                    await client.post(
                        f"{self.base}/api/v1/internal/discord/plugins/voting/jobs/{job['id']}/failed",
                        headers=self.headers, json={"error": str(exc)[:2000]}
                    )

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    async def process(self, job):
        poll = job["poll"]
        guild = self.bot.get_guild(int(poll["guild_id"]))
        if not guild:
            raise RuntimeError("Guild not available to bot.")
        channel = guild.get_channel(int(poll["channel_id"]))
        if not channel:
            raise RuntimeError("Voting channel not found.")
        language = poll["primary_language"]
        text = poll["translations"].get(language) or {}
        embed = discord.Embed(
            title=text.get("title") or "Voting",
            description=text.get("description") or "",
            color=discord.Color.teal(),
        )
        for option in poll.get("options", []):
            ot = option.get("translations", {}).get(language) or {}
            embed.add_field(
                name=f'{option.get("emoji") or ""} {ot.get("label") or "Option"}'.strip(),
                value=f'Votes: {option.get("votes", 0)}', inline=False
            )
        view = None if poll["status"] == "closed" else VotingView(self, poll, language)
        if poll.get("message_id"):
            message = await channel.fetch_message(int(poll["message_id"]))
            await message.edit(embed=embed, view=view)
            message_id = message.id
        else:
            message = await channel.send(embed=embed, view=view)
            message_id = message.id
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base}/api/v1/internal/discord/plugins/voting/jobs/{job['id']}/complete",
                headers=self.headers,
                json={"message_id": message_id},
            )
            response.raise_for_status()
