from __future__ import annotations
import logging
from typing import Any

import discord
import httpx
from discord.ext import tasks

from bot.config import settings
from bot.voting_template_result import fetch_template_result_image

log = logging.getLogger(__name__)

def localized_text(poll: dict, language: str) -> dict:
    return (poll.get("translations", {}).get(language)
            or poll.get("translations", {}).get(poll.get("fallback_language"))
            or poll.get("translations", {}).get(poll.get("primary_language"))
            or {})

def build_embed(poll: dict, language: str) -> discord.Embed:
    text = localized_text(poll, language)
    embed = discord.Embed(
        title=text.get("title") or "Voting",
        description=text.get("description") or "",
        color=discord.Color.teal(),
    )
    for option in poll.get("options", []):
        ot = (option.get("translations", {}).get(language)
              or option.get("translations", {}).get(poll.get("fallback_language"))
              or option.get("translations", {}).get(poll.get("primary_language"))
              or {})
        embed.add_field(
            name=f'{option.get("emoji") or ""} {ot.get("label") or "Option"}'.strip(),
            value=f'Votes: {option.get("votes", 0)}',
            inline=False,
        )
    return embed

class VoteButton(discord.ui.Button):
    def __init__(self, worker, poll_id: str, option_id: str, label: str, language: str, row: int):
        super().__init__(
            label=label[:80], style=discord.ButtonStyle.secondary,
            row=row, custom_id=f"sn_vote:{poll_id}:{option_id}:{language}"
        )
        self.worker, self.poll_id, self.option_id, self.language = worker, poll_id, option_id, language

    async def callback(self, interaction: discord.Interaction):
        try:
            result = await self.worker.submit_vote(
                self.poll_id, self.option_id, interaction.user.id, self.language
            )
            await interaction.response.send_message(
                result.get("message", "Vote recorded."), ephemeral=True
            )
        except Exception:
            log.exception("Voting failed")
            message = "Ошибка голосования."
            locale = interaction.locale.value if interaction.locale else ""
            if locale.startswith("uk"):
                message = "Помилка голосування."
            elif locale.startswith("en"):
                message = "Voting error."
            await interaction.response.send_message(message, ephemeral=True)

class LocalizedVotingView(discord.ui.View):
    def __init__(self, worker, poll: dict, language: str, *, include_language=False):
        super().__init__(timeout=None)
        if include_language and len(poll.get("translations", {})) > 1:
            self.add_item(LanguageSelect(worker, poll))
        row_offset = 1 if include_language and len(poll.get("translations", {})) > 1 else 0
        for index, option in enumerate(poll.get("options", [])):
            translation = (option.get("translations", {}).get(language)
                           or option.get("translations", {}).get(poll["primary_language"]) or {})
            self.add_item(VoteButton(
                worker, poll["id"], option["id"],
                f'{option.get("emoji") or ""} {translation.get("label") or "Option"}'.strip(),
                language, row_offset + index // 5
            ))

class LanguageSelect(discord.ui.Select):
    def __init__(self, worker, poll: dict):
        self.worker, self.poll = worker, poll
        options = [
            discord.SelectOption(label=code.upper(), value=code, emoji="🌐")
            for code in list(poll.get("translations", {}).keys())[:25]
        ]
        super().__init__(
            placeholder="🌐 Select language",
            options=options,
            min_values=1, max_values=1,
            row=0,
            custom_id=f"sn_poll_language:{poll['id']}",
        )

    async def callback(self, interaction: discord.Interaction):
        language = self.values[0]
        await interaction.response.send_message(
            embed=build_embed(self.poll, language),
            view=LocalizedVotingView(self.worker, self.poll, language),
            ephemeral=True,
        )

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
                json={"option_id": option_id, "discord_user_id": user_id, "language_code": language},
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
        closed = poll["status"] == "closed" or job["action"] == "close_result"
        embed = build_embed(poll, language)
        view = None if closed else LocalizedVotingView(self, poll, language, include_language=True)

        if poll.get("message_id"):
            message = await channel.fetch_message(int(poll["message_id"]))
            await message.edit(embed=embed, view=view)
            message_id = message.id
        else:
            message = await channel.send(embed=embed, view=view)
            message_id = message.id

        result_message_id = None
        if closed:
            result_channel_id = (poll.get("result_settings") or {}).get("result_channel_id")
            result_channel = guild.get_channel_or_thread(int(result_channel_id)) if result_channel_id else channel
            if result_channel is None:
                raise RuntimeError("Voting results channel not found.")
            card = await fetch_template_result_image(self, poll) if poll.get("publish_result_image", True) else None
            kwargs: dict[str, Any] = {
                "content": "🏁 **Voting closed — final results**",
                "embed": embed,
            }
            if card is not None:
                kwargs["file"] = discord.File(card, filename=f"poll-{poll['id']}-results.png")
            result_message = await result_channel.send(**kwargs)
            result_message_id = result_message.id

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base}/api/v1/internal/discord/plugins/voting/jobs/{job['id']}/complete",
                headers=self.headers,
                json={"message_id": message_id, "result_message_id": result_message_id},
            )
            response.raise_for_status()
