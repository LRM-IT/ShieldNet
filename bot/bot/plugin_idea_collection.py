"""Persistent survey buttons, private language selection and idea forms."""
import logging
import re
import discord
import httpx
from discord.ext import tasks
from bot.config import settings

log = logging.getLogger(__name__)


def language_for(survey, role_ids, groups, locale):
    available = survey["translations"]
    matches = []
    for group in groups:
        if not group.get("enabled", True):
            continue
        for code, role in (group.get("language_roles") or {}).items():
            if code in available and str(role) in role_ids and code not in matches:
                matches.append(code)
    locale = str(locale).lower()
    preferred = next((code for code in available if code.lower() == locale), None)
    preferred = preferred or next((code for code in available if code == locale.split("-")[0]), None)
    if len(matches) == 1:
        return matches[0]
    return (preferred if preferred in matches else matches[0]) if matches else preferred or survey["primary_language"]


def embed(survey, language):
    text = survey["translations"][language]
    result = discord.Embed(title="💡 " + text["title"], description=text["description"], color=0x21CBB8)
    # Stable marker allows recovery if Discord accepted a send but acknowledgement failed.
    result.set_footer(text="GuildConsole · " + survey["id"])
    return result


async def unavailable(interaction):
    messages = {"ru": "Опрос недоступен или закрыт. Попробуйте позже.",
                "uk": "Опитування недоступне або закрите. Спробуйте пізніше."}
    text = messages.get(str(interaction.locale).split("-")[0], "This survey is unavailable or closed. Please try again later.")
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


class IdeaModal(discord.ui.Modal):
    def __init__(self, worker, survey, language, user_id):
        text = survey["translations"][language]
        super().__init__(title=text["title"], timeout=600)
        self.worker, self.survey, self.language, self.user_id = worker, survey, language, user_id
        self.idea = discord.ui.TextInput(label=text["label"], placeholder=text["placeholder"],
                                        style=discord.TextStyle.paragraph, min_length=1, max_length=4000)
        self.add_item(self.idea)

    async def on_submit(self, interaction):
        if interaction.user.id != self.user_id or str(interaction.guild_id) != self.survey["guild_id"]:
            return await unavailable(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self.worker.request("POST", interaction.guild_id, f"/{self.survey['id']}/answer", {
                "user_id": interaction.user.id, "display_name": interaction.user.display_name,
                "language": self.language, "text": str(self.idea.value)})
            await interaction.followup.send(self.survey["translations"][self.language]["thanks"],
                                            ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            log.exception("Idea response failed survey=%s", self.survey["id"])
            await unavailable(interaction)


class OpenForm(discord.ui.Button):
    def __init__(self, worker, survey, language):
        super().__init__(label=survey["translations"][language]["button"], emoji="💡", style=discord.ButtonStyle.success)
        self.worker, self.survey, self.language = worker, survey, language

    async def callback(self, interaction):
        # Configuration was loaded for this private view. Submission rechecks enabled/closed state.
        await interaction.response.send_modal(IdeaModal(self.worker, self.survey, self.language, interaction.user.id))


class LanguageSelect(discord.ui.Select):
    def __init__(self, worker, survey):
        super().__init__(placeholder="🌐 Language", options=[discord.SelectOption(label=code.upper(), value=code)
                                                           for code in survey["translations"]])
        self.worker, self.survey = worker, survey

    async def callback(self, interaction):
        language = self.values[0]
        await interaction.response.edit_message(embed=embed(self.survey, language),
                                                 view=private_view(self.worker, self.survey, language))


def private_view(worker, survey, language):
    view = discord.ui.View(timeout=600)
    if len(survey["translations"]) > 1:
        view.add_item(LanguageSelect(worker, survey))
    view.add_item(OpenForm(worker, survey, language))
    return view


class SurveyButton(discord.ui.DynamicItem[discord.ui.Button], template=r"gc_idea:(?P<survey>[0-9a-f-]{36})"):
    def __init__(self, survey_id, label="Answer now"):
        self.survey_id = survey_id
        super().__init__(discord.ui.Button(label=label, emoji="💡", style=discord.ButtonStyle.success,
                                          custom_id=f"gc_idea:{survey_id}"))

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match):
        return cls(match["survey"], item.label)

    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        worker = interaction.client.idea_collection
        try:
            if not interaction.guild or interaction.guild not in interaction.client.managed_guilds:
                return await unavailable(interaction)
            survey = await worker.request("GET", interaction.guild_id, f"/{self.survey_id}")
            if str(interaction.message.id) != survey["message_id"]:
                return await unavailable(interaction)
            groups = []
            try:
                config = await interaction.client.language_selection.configuration(interaction.guild_id)
                groups = config.get("groups", []) if config.get("enabled") else []
            except Exception:
                log.warning("Language roles unavailable; using Discord locale")
            code = language_for(survey, {str(r.id) for r in getattr(interaction.user, "roles", [])}, groups, interaction.locale)
            await interaction.followup.send(embed=embed(survey, code), view=private_view(worker, survey, code), ephemeral=True)
        except Exception:
            log.exception("Unable to open idea survey")
            await unavailable(interaction)


class IdeaCollectionWorker:
    def __init__(self, bot):
        self.bot = bot
        self.base = settings.backend_url.rstrip("/") + "/api/v1/internal/idea-collection/guilds"
        self.headers = {"X-ShieldNet-Service-Token": settings.internal_service_token}

    async def request(self, method, guild_id, path, payload=None):
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.request(method, f"{self.base}/{guild_id}{path}", headers=self.headers, json=payload)
            r.raise_for_status()
            return r.json()

    @tasks.loop(seconds=10)
    async def loop(self):
        for guild in self.bot.managed_guilds:
            try:
                job = await self.request("POST", guild.id, "/claim")
                if job.get("item"):
                    await self.process(guild, job)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 409:
                    log.exception("Idea survey queue failed guild=%s", guild.id)
            except Exception:
                log.exception("Idea survey queue failed guild=%s", guild.id)

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    async def process(self, guild, job):
        survey = job["item"]
        result = {"claim_id": job["claim_id"]}
        try:
            channel = guild.get_channel_or_thread(int(survey["channel_id"])) or await self.bot.fetch_channel(int(survey["channel_id"]))
            if not isinstance(channel, (discord.TextChannel, discord.Thread)) or channel.guild.id != guild.id:
                raise ValueError("Select a text channel or an existing forum thread")
            message = None
            if survey["message_id"]:
                try:
                    message = await channel.fetch_message(int(survey["message_id"]))
                except discord.NotFound:
                    pass
            elif survey["active"]:
                async for candidate in channel.history(limit=100):
                    if candidate.author.id == self.bot.user.id and any(
                        x.footer.text == "GuildConsole · " + survey["id"] for x in candidate.embeds):
                        message = candidate
                        break
            view = None
            if survey["active"]:
                view = discord.ui.View(timeout=None)
                view.add_item(SurveyButton(survey["id"], survey["translations"][survey["primary_language"]]["button"]))
            if message:
                await message.edit(embed=embed(survey, survey["primary_language"]), view=view, allowed_mentions=discord.AllowedMentions.none())
            elif survey["active"]:
                message = await channel.send(embed=embed(survey, survey["primary_language"]), view=view, allowed_mentions=discord.AllowedMentions.none())
            result["message_id"] = message.id if message else None
        except Exception as exc:
            log.exception("Survey publication failed")
            result["error"] = str(exc)[:1000]
        # Failed acknowledgement leaves a recoverable lease, not a second publication.
        await self.request("POST", guild.id, f"/{survey['id']}/complete", result)
