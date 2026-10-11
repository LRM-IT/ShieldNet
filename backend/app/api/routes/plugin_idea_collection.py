from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict, ValidationError, model_validator
from sqlalchemy import select, func, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.core import User
from app.models.plugins import GuildPluginInstallation
from app.models.explorer import GuildChannel
from app.models.plugin_idea_collection import IdeaSurvey, IdeaResponse
from app.models.global_languages import GlobalLanguage
from app.services.ai_runtime import AIRuntimeService

router = APIRouter(prefix="/discord/guilds/{guild_id}/plugins/idea-collection", tags=["Idea Collection"])
internal_router = APIRouter(prefix="/internal/idea-collection/guilds/{guild_id}", dependencies=[Depends(verify_internal_service_token)])


async def serialize_for_bot(session, row):
    data = serialize(row)
    languages = (await session.scalars(select(GlobalLanguage).where(
        GlobalLanguage.code.in_(data['translations'])))).all()
    data['language_labels'] = {language.code: {'name': language.name, 'flag': language.flag}
                               for language in languages}
    return data


class SurveyText(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=4096)
    button: str = Field(default="Answer now", min_length=1, max_length=80)
    label: str = Field(default="Your idea", min_length=1, max_length=45)
    placeholder: str = Field(default="What would you like to see on our server?", max_length=100)
    thanks: str = Field(default="Thank you! Your idea has been sent to the server team.", min_length=1, max_length=2000)


class SurveyInput(BaseModel):
    channel_id: str = Field(pattern=r"^[0-9]{15,19}$")
    primary_language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z]{2,4})?$")
    translations: dict[str, SurveyText] = Field(min_length=1, max_length=25)

    @model_validator(mode="after")
    def validate_languages(self):
        if self.primary_language not in self.translations:
            raise ValueError("Primary language text is required")
        if any(not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?", code) for code in self.translations):
            raise ValueError("Invalid language code")
        if int(self.channel_id) > 2**63-1:
            raise ValueError("Invalid channel ID")
        return self


class TranslateInput(BaseModel):
    source_language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z]{2,4})?$")
    target_language: str = Field(pattern=r"^[a-z]{2,3}(?:-[A-Za-z]{2,4})?$")
    text: SurveyText


async def installation(session, guild_id, enabled=False):
    item = await session.scalar(select(GuildPluginInstallation).where(
        GuildPluginInstallation.guild_id == guild_id, GuildPluginInstallation.plugin_key == "idea_collection"))
    if not item or (enabled and not item.enabled):
        raise HTTPException(409, "Install and enable Idea Collection first")
    return item


async def survey_row(session, guild_id, survey_id, lock=False):
    q = select(IdeaSurvey).where(IdeaSurvey.id == survey_id, IdeaSurvey.guild_id == guild_id)
    row = await session.scalar(q.with_for_update() if lock else q)
    if not row:
        raise HTTPException(404, "Survey not found")
    return row


def serialize(row):
    return {"id": str(row.id), "guild_id": str(row.guild_id), **row.configuration,
            "active": row.active, "message_id": str(row.message_id) if row.message_id else None,
            "job_status": row.job_status, "error": row.error, "created_at": row.created_at}


async def check_channel(session, guild_id, channel_id):
    channel = await session.scalar(select(GuildChannel).where(GuildChannel.guild_id == guild_id,
                                  GuildChannel.discord_channel_id == int(channel_id)))
    if not channel or channel.channel_type not in {"text", "news", "public_thread", "private_thread", "news_thread"}:
        raise HTTPException(422, "Select a text channel or an existing thread, not a forum category")


@router.get("")
async def listing(guild_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    item = await session.scalar(select(GuildPluginInstallation).where(GuildPluginInstallation.guild_id == guild_id,
                                                                     GuildPluginInstallation.plugin_key == "idea_collection"))
    rows = (await session.scalars(select(IdeaSurvey).where(IdeaSurvey.guild_id == guild_id).order_by(IdeaSurvey.created_at.desc()))).all()
    counts = dict((await session.execute(select(IdeaResponse.survey_id, func.count()).join(IdeaSurvey)
                  .where(IdeaSurvey.guild_id == guild_id).group_by(IdeaResponse.survey_id))).all())
    return {"installed": bool(item), "enabled": bool(item and item.enabled),
            "items": [{**serialize(row), "response_count": counts.get(row.id, 0)} for row in rows]}


@router.post("")
async def create(guild_id: int, payload: SurveyInput, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    await installation(session, guild_id)
    await check_channel(session, guild_id, payload.channel_id)
    row = IdeaSurvey(guild_id=guild_id, configuration=payload.model_dump())
    session.add(row)
    await session.commit()
    return serialize(row)


@router.put("/{survey_id}")
async def save(guild_id: int, survey_id: UUID, payload: SurveyInput, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    await installation(session, guild_id)
    row = await survey_row(session, guild_id, survey_id, True)
    if row.job_status in {"pending", "processing"}:
        raise HTTPException(409, "Wait for publication to finish")
    if row.message_id and row.configuration["channel_id"] != payload.channel_id:
        raise HTTPException(422, "Create a new survey to change the published channel")
    await check_channel(session, guild_id, payload.channel_id)
    row.configuration = payload.model_dump()
    await session.commit()
    return serialize(row)


@router.post("/translate")
async def translate(guild_id: int, payload: TranslateInput, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    await installation(session, guild_id)
    result = {}
    try:
        for field, value in payload.text.model_dump().items():
            limit = SurveyText.model_fields[field].metadata
            max_length = next((x.max_length for x in limit if hasattr(x, "max_length")), 4000)
            result[field] = await AIRuntimeService(session).translate(guild_id=guild_id, module_key="idea_collection",
                text=value, source_language=payload.source_language, target_language=payload.target_language,
                system_prompt=f"Return only the translated text. Keep it within {max_length} characters. Use concise natural wording for UI labels; preserve the meaning.",
                metadata={"field": field}) if value and payload.source_language != payload.target_language else value
        try:
            return SurveyText.model_validate(result)
        except ValidationError as exc:
            # Preserve paid-for translations so the administrator can fix a long
            # label instead of losing every translated field and paying again.
            return {**result, "warnings": [{"loc": ["translations", payload.target_language, *e["loc"]],
                    "type": e["type"], "ctx": e.get("ctx", {})} for e in exc.errors()]}
    except (LookupError, RuntimeError, ValueError) as exc:
        raise HTTPException(422, "Translation failed. Check the AI Center translation route and text length.") from exc


@router.post("/{survey_id}/{action}")
async def publish(guild_id: int, survey_id: UUID, action: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    if action not in {"publish", "close"}:
        raise HTTPException(404)
    await installation(session, guild_id, enabled=action == "publish")
    row = await survey_row(session, guild_id, survey_id, True)
    if row.job_status == "processing":
        raise HTTPException(409, "Wait for publication to finish")
    row.active = action == "publish"
    row.job_status = "pending"
    row.error = None
    await session.commit()
    return serialize(row)


@router.get("/{survey_id}/responses")
async def responses(guild_id: int, survey_id: UUID, offset: int = Query(0, ge=0), user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    await require_guild_module(session, user, guild_id, "plugins")
    await survey_row(session, guild_id, survey_id)
    rows = (await session.scalars(select(IdeaResponse).where(IdeaResponse.survey_id == survey_id)
                   .order_by(IdeaResponse.updated_at.desc(), IdeaResponse.user_id).offset(offset).limit(50))).all()
    total = await session.scalar(select(func.count()).select_from(IdeaResponse).where(IdeaResponse.survey_id == survey_id))
    return {"total": total, "items": [{"user_id": str(x.user_id), "display_name": x.display_name,
            "language": x.language, "text": x.text, "updated_at": x.updated_at} for x in rows]}


@internal_router.post("/claim")
async def claim(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    # A worker only polls its managed guilds. Leases survive process restarts.
    item = await installation(session, guild_id)
    row = await session.scalar(select(IdeaSurvey).where(IdeaSurvey.guild_id == guild_id,
        or_(IdeaSurvey.job_status == "pending", (IdeaSurvey.job_status == "processing") &
            (IdeaSurvey.claimed_at < datetime.now(UTC) - timedelta(minutes=5))))
        .order_by(IdeaSurvey.created_at).with_for_update(skip_locked=True).limit(1))
    if not row:
        return {"item": None}
    if row.active and not item.enabled:
        row.job_status = "failed"
        row.error = "Enable Idea Collection before publishing"
        await session.commit()
        return {"item": None}
    row.job_status, row.claim_id, row.claimed_at = "processing", uuid4(), datetime.now(UTC)
    await session.commit()
    return {"item": await serialize_for_bot(session, row), "claim_id": str(row.claim_id)}


class CompleteInput(BaseModel):
    claim_id: UUID
    message_id: int | None = Field(default=None, gt=0, le=2**63-1)
    error: str | None = Field(default=None, max_length=1000)


@internal_router.post("/{survey_id}/complete")
async def complete(guild_id: int, survey_id: UUID, payload: CompleteInput, session: AsyncSession = Depends(get_db_session)):
    row = await survey_row(session, guild_id, survey_id, True)
    if row.claim_id != payload.claim_id or row.job_status != "processing":
        raise HTTPException(409, "Publication lease expired")
    if payload.message_id:
        row.message_id = payload.message_id
    row.error = payload.error
    row.job_status = "failed" if payload.error else "published" if row.active else "closed"
    await session.commit()
    return {"ok": True}


@internal_router.get("/{survey_id}")
async def internal_survey(guild_id: int, survey_id: UUID, session: AsyncSession = Depends(get_db_session)):
    await installation(session, guild_id, True)
    row = await survey_row(session, guild_id, survey_id)
    if not row.active or not row.message_id:
        raise HTTPException(409, "This survey is closed or unavailable")
    return await serialize_for_bot(session, row)


class AnswerInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    user_id: int = Field(gt=0, le=2**63-1)
    display_name: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=2, max_length=16)
    text: str = Field(min_length=1, max_length=4000)


@internal_router.post("/{survey_id}/answer")
async def answer(guild_id: int, survey_id: UUID, payload: AnswerInput, session: AsyncSession = Depends(get_db_session)):
    await installation(session, guild_id, True)
    row = await survey_row(session, guild_id, survey_id, True)
    if not row.active or not row.message_id:
        raise HTTPException(409, "This survey is closed or unavailable")
    if payload.language not in row.configuration["translations"]:
        raise HTTPException(422, "Unsupported survey language")
    # One editable answer per member. Retried submissions cannot create duplicates.
    values = payload.model_dump()
    await session.execute(insert(IdeaResponse).values(survey_id=survey_id, **values)
        .on_conflict_do_update(index_elements=["survey_id", "user_id"], set_={**values, "updated_at": datetime.now(UTC)}))
    await session.commit()
    return {"ok": True}
