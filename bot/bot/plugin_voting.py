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

def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _gradient(image: Image.Image, top: tuple[int, int, int], bottom: tuple[int, int, int]):
    draw = ImageDraw.Draw(image)
    w, h = image.size
    for y in range(h):
        k = y / max(h - 1, 1)
        color = tuple(int(top[i] * (1 - k) + bottom[i] * k) for i in range(3))
        draw.line((0, y, w, y), fill=color)


def _draw_commander(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0):
    # Generic sci-fi commander silhouette.
    c1, c2, glow = (17, 27, 40), (31, 52, 67), (53, 226, 178)
    r = int(34 * scale)
    draw.ellipse((x-r, y-r, x+r, y+r), fill=c2, outline=glow, width=max(2, int(3*scale)))
    draw.rounded_rectangle(
        (x-int(58*scale), y+int(28*scale), x+int(58*scale), y+int(150*scale)),
        radius=int(22*scale), fill=c1, outline=glow, width=max(2, int(3*scale))
    )
    draw.polygon([
        (x-int(58*scale), y+int(58*scale)),
        (x-int(112*scale), y+int(120*scale)),
        (x-int(70*scale), y+int(138*scale)),
        (x-int(28*scale), y+int(78*scale)),
    ], fill=c2)
    draw.polygon([
        (x+int(58*scale), y+int(58*scale)),
        (x+int(112*scale), y+int(120*scale)),
        (x+int(70*scale), y+int(138*scale)),
        (x+int(28*scale), y+int(78*scale)),
    ], fill=c2)
    # visor
    draw.rounded_rectangle(
        (x-int(23*scale), y-int(8*scale), x+int(23*scale), y+int(5*scale)),
        radius=int(6*scale), fill=glow
    )


def _draw_city(draw: ImageDraw.ImageDraw, width: int, base_y: int):
    buildings = [
        (0, 155, 86), (92, 115, 73), (171, 185, 110), (291, 105, 62),
        (360, 220, 95), (465, 135, 72), (548, 180, 100), (660, 120, 60),
        (735, 205, 115), (858, 140, 84), (955, 190, 102), (1065, 125, 68)
    ]
    for x, h, w in buildings:
        draw.rectangle((x, base_y-h, x+w, base_y), fill=(8, 18, 29))
        for yy in range(base_y-h+18, base_y-10, 24):
            for xx in range(x+12, x+w-8, 22):
                draw.rectangle((xx, yy, xx+5, yy+8), fill=(31, 105, 109))


def result_card(poll: dict, language: str) -> io.BytesIO:
    settings_data = poll.get("result_settings") or {}
    theme = str(settings_data.get("theme") or "ShieldNet")
    prompt = str(settings_data.get("theme_prompt") or "").strip()
    title = localized_text(poll, language).get("title") or "Voting results"
    options = poll.get("options", [])
    total = sum(int(x.get("votes", 0)) for x in options)

    width = 1600
    height = max(900, 470 + len(options) * 92)
    image = Image.new("RGB", (width, height))
    _gradient(image, (7, 17, 28), (2, 7, 13))
    draw = ImageDraw.Draw(image)

    # Cinematic background.
    for i in range(55):
        x = (i * 137) % width
        y = 40 + ((i * 79) % 360)
        r = 1 + (i % 3)
        draw.ellipse((x-r, y-r, x+r, y+r), fill=(95, 190, 185))
    draw.ellipse((1210, 60, 1500, 350), fill=(22, 69, 86), outline=(53, 226, 178), width=3)
    draw.ellipse((1260, 105, 1450, 295), fill=(8, 26, 39))
    _draw_city(draw, width, 520)

    # Character composition.
    _draw_commander(draw, 1320, 360, 1.45)
    _draw_commander(draw, 1155, 420, 0.92)
    _draw_commander(draw, 1485, 425, 0.88)

    # Main glass panel.
    draw.rounded_rectangle(
        (45, 42, width-45, height-42),
        radius=34, fill=(7, 21, 31, 255), outline=(53, 226, 178), width=4
    )
    draw.rounded_rectangle(
        (70, 68, 1050, 430),
        radius=26, fill=(10, 29, 40), outline=(27, 87, 93), width=2
    )

    eyebrow = _font(24, True)
    title_font = _font(52, True)
    subtitle_font = _font(25, False)
    option_font = _font(28, True)
    small_font = _font(22, False)
    number_font = _font(30, True)

    draw.text((95, 95), theme.upper(), fill=(53, 226, 178), font=eyebrow)
    draw.text((95, 145), title[:58], fill=(242, 250, 248), font=title_font)
    if prompt:
        draw.text((95, 220), prompt[:82], fill=(137, 165, 176), font=subtitle_font)
    draw.text((95, 285), f"FINAL RESULTS  •  {total} VOTES", fill=(122, 151, 164), font=subtitle_font)

    # Trophy / winner mark.
    winner_votes = max([int(x.get("votes", 0)) for x in options] or [0])
    draw.rounded_rectangle((95, 335, 445, 405), radius=18, fill=(17, 47, 55), outline=(53, 226, 178), width=2)
    draw.text((125, 354), "🏆  WINNER HIGHLIGHT", fill=(53, 226, 178), font=small_font)

    # Results board.
    board_top = 470
    draw.rounded_rectangle(
        (70, board_top, width-70, height-90),
        radius=28, fill=(8, 25, 35), outline=(29, 71, 80), width=2
    )
    y = board_top + 34
    max_votes = max(winner_votes, 1)

    for index, option in enumerate(options):
        ot = (
            option.get("translations", {}).get(language)
            or option.get("translations", {}).get(poll.get("primary_language"))
            or {}
        )
        label = str(ot.get("label") or f"Option {index+1}")
        votes = int(option.get("votes", 0))
        pct = (votes / total * 100) if total else 0
        winner = votes == winner_votes and winner_votes > 0

        card_fill = (14, 39, 48) if not winner else (15, 54, 53)
        outline = (31, 73, 83) if not winner else (53, 226, 178)
        draw.rounded_rectangle(
            (95, y, width-95, y+68),
            radius=18, fill=card_fill, outline=outline, width=2
        )
        rank_color = (53, 226, 178) if winner else (133, 160, 171)
        draw.text((120, y+15), f"{index+1}", fill=rank_color, font=number_font)
        draw.text((180, y+18), label[:54], fill=(238, 247, 244), font=option_font)

        bar_x1, bar_x2 = 720, 1320
        draw.rounded_rectangle((bar_x1, y+22, bar_x2, y+46), radius=12, fill=(24, 52, 61))
        fill_w = int((bar_x2 - bar_x1) * votes / max_votes) if votes else 0
        if fill_w:
            draw.rounded_rectangle(
                (bar_x1, y+22, bar_x1+fill_w, y+46),
                radius=12, fill=(53, 226, 178)
            )

        draw.text((1350, y+15), f"{votes}", fill=(242, 250, 248), font=number_font)
        draw.text((1430, y+18), f"{pct:.1f}%", fill=(138, 166, 177), font=small_font)
        y += 88

    draw.text((95, height-72), "Generated by ShieldNet • Secure Voting System", fill=(92, 120, 130), font=small_font)
    draw.text((width-420, height-72), "MULTIMEDIA RESULT POSTER", fill=(53, 226, 178), font=small_font)

    out = io.BytesIO()
    image.save(out, format="PNG", quality=95)
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
