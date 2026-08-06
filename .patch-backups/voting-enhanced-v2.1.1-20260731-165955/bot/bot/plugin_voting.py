from __future__ import annotations
import io
import logging
from typing import Any

import discord
import httpx
from discord.ext import tasks
from PIL import Image, ImageDraw, ImageFont

from bot.config import settings

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
        except Exception as exc:
            log.exception("Voting failed")
            await interaction.response.send_message(
                f"Unable to record vote: {str(exc)[:180]}", ephemeral=True
            )

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

def result_card(poll: dict, language: str) -> io.BytesIO:
    settings = poll.get("result_settings") or {}
    theme = str(settings.get("theme") or "ShieldNet")
    title = localized_text(poll, language).get("title") or "Voting results"
    options = poll.get("options", [])
    total = sum(int(x.get("votes", 0)) for x in options)
    width, height = 1200, max(675, 300 + len(options) * 78)
    image = Image.new("RGB", (width, height), (5, 12, 18))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.rounded_rectangle((28, 28, width-28, height-28), radius=26, fill=(11, 25, 34), outline=(53, 226, 178), width=3)
    draw.text((70, 65), theme.upper(), fill=(53, 226, 178), font=font)
    draw.text((70, 105), title[:110], fill=(240, 250, 247), font=font)
    draw.text((70, 145), f"FINAL RESULTS · {total} VOTES", fill=(135, 160, 170), font=font)
    y = 215
    max_votes = max([int(x.get("votes", 0)) for x in options] or [1])
    for index, option in enumerate(options):
        ot = (option.get("translations", {}).get(language)
              or option.get("translations", {}).get(poll.get("primary_language")) or {})
        label = str(ot.get("label") or f"Option {index+1}")
        votes = int(option.get("votes", 0))
        pct = (votes / total * 100) if total else 0
        draw.text((75, y), f"{index+1}. {label[:70]}", fill=(235, 245, 242), font=font)
        draw.rounded_rectangle((430, y, 1020, y+24), radius=12, fill=(20, 43, 51))
        fill_w = int(590 * (votes / max_votes)) if max_votes else 0
        if fill_w:
            draw.rounded_rectangle((430, y, 430+fill_w, y+24), radius=12, fill=(53, 226, 178))
        draw.text((1040, y), f"{votes} · {pct:.1f}%", fill=(235, 245, 242), font=font)
        y += 78
    draw.text((70, height-85), "Generated by ShieldNet", fill=(90, 115, 125), font=font)
    out = io.BytesIO()
    image.save(out, format="PNG")
    out.seek(0)
    return out

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
        settings_data = poll.get("result_settings") or {}
        if closed and settings_data.get("publish_result_image", True):
            card = result_card(poll, language)
            result_message = await channel.send(
                content="🏁 **Voting closed — final results**",
                file=discord.File(card, filename=f"poll-{poll['id']}-results.png"),
            )
            result_message_id = result_message.id

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base}/api/v1/internal/discord/plugins/voting/jobs/{job['id']}/complete",
                headers=self.headers,
                json={"message_id": message_id, "result_message_id": result_message_id},
            )
            response.raise_for_status()
