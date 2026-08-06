from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_management
from app.db.session import get_db_session
from app.models.core import User
from app.models.plugin_voting import (
    VotingOption, VotingOptionTranslation, VotingPoll, VotingPollTranslation,
    VotingPublicationJob, VotingVote,
)
from app.services.ai_runtime import AIRuntimeService

router = APIRouter(tags=["Voting Plugin"])


class OptionIn(BaseModel):
    emoji: str | None = None
    translations: dict[str, str]


class PollCreate(BaseModel):
    primary_language: str = "en"
    fallback_language: str = "en"
    language_selection_mode: str = "automatic_with_selector"
    channel_id: int | str | None = None
    selection_mode: str = "single"
    anonymous: bool = True
    allow_change_vote: bool = True
    show_live_results: bool = True
    min_choices: int = 1
    max_choices: int = 1
    allowed_role_ids: list[int] = Field(default_factory=list)
    closes_at: datetime | None = None
    result_settings: dict = Field(default_factory=dict)
    translations: dict[str, dict[str, str | None]]
    options: list[OptionIn]



class TranslationPreview(BaseModel):
    source_language: str
    target_language: str
    title: str
    description: str | None = None
    options: list[str] = Field(default_factory=list)

class TranslationGenerate(BaseModel):
    source_language: str | None = None
    overwrite_existing: bool = False


async def get_poll_row(session: AsyncSession, guild_id: int, poll_id: UUID) -> VotingPoll:
    poll = (await session.execute(select(VotingPoll).where(
        VotingPoll.id == poll_id, VotingPoll.guild_id == guild_id
    ))).scalar_one_or_none()
    if not poll:
        raise HTTPException(404, "Poll not found.")
    return poll


async def serialize_poll(session: AsyncSession, poll: VotingPoll):
    translations = list((await session.execute(
        select(VotingPollTranslation).where(VotingPollTranslation.poll_id == poll.id)
    )).scalars())
    options = list((await session.execute(
        select(VotingOption).where(VotingOption.poll_id == poll.id).order_by(VotingOption.position)
    )).scalars())
    option_ids = [x.id for x in options]
    option_translations = list((await session.execute(
        select(VotingOptionTranslation).where(
            VotingOptionTranslation.option_id.in_(option_ids or [UUID(int=0)])
        )
    )).scalars())
    counts = dict((await session.execute(
        select(VotingVote.option_id, func.count(VotingVote.id))
        .where(VotingVote.poll_id == poll.id)
        .group_by(VotingVote.option_id)
    )).all())
    return {
        "id": str(poll.id), "guild_id": str(poll.guild_id), "status": poll.status,
        "channel_id": str(poll.channel_id) if poll.channel_id else None,
        "message_id": str(poll.message_id) if poll.message_id else None,
        "primary_language": poll.primary_language,
        "fallback_language": poll.fallback_language,
        "language_selection_mode": poll.language_selection_mode,
        "selection_mode": poll.selection_mode, "anonymous": poll.anonymous,
        "allow_change_vote": poll.allow_change_vote,
        "show_live_results": poll.show_live_results,
        "min_choices": poll.min_choices, "max_choices": poll.max_choices,
        "allowed_role_ids": [str(x) for x in (poll.allowed_role_ids or [])],
        "closes_at": poll.closes_at,
        "result_settings": poll.result_settings or {},
        "result_message_id": str(poll.result_message_id) if getattr(poll, "result_message_id", None) else None,
        "translations": {
            t.language_code: {
                "title": t.title, "description": t.description,
                "completion_message": t.completion_message,
                "source": t.translation_source, "reviewed": t.reviewed,
                "ai_provider": t.ai_provider, "ai_model": t.ai_model,
            } for t in translations
        },
        "options": [{
            "id": str(o.id), "position": o.position, "emoji": o.emoji,
            "votes": int(counts.get(o.id, 0)),
            "translations": {
                t.language_code: {"label": t.label, "description": t.description}
                for t in option_translations if t.option_id == o.id
            }
        } for o in options]
    }


async def apply_payload(session: AsyncSession, poll: VotingPoll, payload: PollCreate) -> None:
    if not 2 <= len(payload.options) <= 10:
        raise HTTPException(422, "A poll must contain 2-10 options.")
    if payload.primary_language not in payload.translations:
        raise HTTPException(422, "Primary language translation is required.")

    poll.primary_language = payload.primary_language
    poll.fallback_language = payload.fallback_language
    poll.language_selection_mode = payload.language_selection_mode
    poll.channel_id = int(payload.channel_id) if payload.channel_id else None
    poll.selection_mode = payload.selection_mode
    poll.anonymous = payload.anonymous
    poll.allow_change_vote = payload.allow_change_vote
    poll.show_live_results = payload.show_live_results
    poll.min_choices = payload.min_choices
    poll.max_choices = payload.max_choices
    poll.allowed_role_ids = [int(x) for x in payload.allowed_role_ids]
    poll.closes_at = payload.closes_at
    poll.result_settings = payload.result_settings or {}

    await session.execute(delete(VotingPollTranslation).where(VotingPollTranslation.poll_id == poll.id))
    existing_options = list((await session.execute(
        select(VotingOption).where(VotingOption.poll_id == poll.id)
    )).scalars())
    existing_ids = [x.id for x in existing_options]
    if existing_ids:
        await session.execute(delete(VotingOptionTranslation).where(
            VotingOptionTranslation.option_id.in_(existing_ids)
        ))
    await session.execute(delete(VotingOption).where(VotingOption.poll_id == poll.id))

    for language, text in payload.translations.items():
        title = str(text.get("title") or "").strip()
        if not title:
            raise HTTPException(422, f"Title is required for {language}.")
        session.add(VotingPollTranslation(
            poll_id=poll.id, language_code=language, title=title,
            description=text.get("description"),
            completion_message=text.get("completion_message"),
            translation_source="primary" if language == payload.primary_language else "manual",
            reviewed=language == payload.primary_language,
        ))
    for index, item in enumerate(payload.options):
        option = VotingOption(poll_id=poll.id, position=index, emoji=item.emoji)
        session.add(option)
        await session.flush()
        for language, label in item.translations.items():
            value = str(label or "").strip()
            if not value:
                raise HTTPException(422, f"Option {index + 1} is empty for {language}.")
            session.add(VotingOptionTranslation(
                option_id=option.id, language_code=language, label=value
            ))


@router.get("/discord/guilds/{guild_id}/plugins/voting/polls")
async def list_polls(guild_id: int, current_user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    polls = list((await session.execute(
        select(VotingPoll).where(VotingPoll.guild_id == guild_id)
        .order_by(VotingPoll.created_at.desc())
    )).scalars())
    return {"items": [await serialize_poll(session, x) for x in polls]}


@router.post("/discord/guilds/{guild_id}/plugins/voting/polls")
async def create_poll(guild_id: int, payload: PollCreate,
                      current_user: User = Depends(get_current_user),
                      session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    poll = VotingPoll(guild_id=guild_id, created_by_user_id=getattr(current_user, "id", None))
    session.add(poll)
    await session.flush()
    await apply_payload(session, poll, payload)
    await session.commit()
    await session.refresh(poll)
    return await serialize_poll(session, poll)


@router.get("/discord/guilds/{guild_id}/plugins/voting/polls/{poll_id}")
async def get_poll(guild_id: int, poll_id: UUID,
                   current_user: User = Depends(get_current_user),
                   session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    return await serialize_poll(session, await get_poll_row(session, guild_id, poll_id))


@router.put("/discord/guilds/{guild_id}/plugins/voting/polls/{poll_id}")
async def update_poll(guild_id: int, poll_id: UUID, payload: PollCreate,
                      current_user: User = Depends(get_current_user),
                      session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    poll = await get_poll_row(session, guild_id, poll_id)
    if poll.status == "closed":
        raise HTTPException(409, "Closed polls cannot be edited.")
    await apply_payload(session, poll, payload)
    if poll.message_id:
        session.add(VotingPublicationJob(poll_id=poll.id, action="refresh"))
    await session.commit()
    await session.refresh(poll)
    return await serialize_poll(session, poll)


@router.delete("/discord/guilds/{guild_id}/plugins/voting/polls/{poll_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_poll(guild_id: int, poll_id: UUID,
                      current_user: User = Depends(get_current_user),
                      session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    poll = await get_poll_row(session, guild_id, poll_id)
    await session.delete(poll)
    await session.commit()
    return Response(status_code=204)


@router.post("/discord/guilds/{guild_id}/plugins/voting/polls/{poll_id}/publish")
async def publish_poll(guild_id: int, poll_id: UUID,
                       current_user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    poll = await get_poll_row(session, guild_id, poll_id)
    if not poll.channel_id:
        raise HTTPException(422, "Select a Discord channel.")
    poll.status = "publishing"
    session.add(VotingPublicationJob(poll_id=poll.id, action="publish"))
    await session.commit()
    return {"status": "queued", "poll_id": str(poll.id)}


@router.post("/discord/guilds/{guild_id}/plugins/voting/polls/{poll_id}/close")
async def close_poll(guild_id: int, poll_id: UUID,
                     current_user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    poll = await get_poll_row(session, guild_id, poll_id)
    poll.status = "closed"
    poll.closed_at = datetime.now(UTC)
    session.add(VotingPublicationJob(poll_id=poll.id, action="close_result"))
    await session.commit()
    return {"status": "closed"}



@router.post("/discord/guilds/{guild_id}/plugins/voting/translations/preview")
async def preview_translation(guild_id: int, payload: TranslationPreview,
                              current_user: User = Depends(get_current_user),
                              session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    source = payload.source_language.strip().lower()
    target = payload.target_language.strip().lower()
    if not payload.title.strip():
        raise HTTPException(422, "Source title is required.")
    if source == target:
        return {
            "status": "translated",
            "source_language": source,
            "target_language": target,
            "translation": {
                "title": payload.title,
                "description": payload.description,
            },
            "options": [{"position": i, "label": text} for i, text in enumerate(payload.options)],
        }

    runtime = AIRuntimeService(session)
    title = await runtime.translate(
        guild_id=guild_id, module_key="voting",
        text=payload.title, source_language=source, target_language=target,
        metadata={"mode": "preview", "field": "title"},
    )
    description = None
    if payload.description and payload.description.strip():
        description = await runtime.translate(
            guild_id=guild_id, module_key="voting",
            text=payload.description, source_language=source, target_language=target,
            metadata={"mode": "preview", "field": "description"},
        )

    translated_options = []
    for index, text in enumerate(payload.options):
        if not str(text or "").strip():
            translated_options.append({"position": index, "label": ""})
            continue
        label = await runtime.translate(
            guild_id=guild_id, module_key="voting",
            text=text, source_language=source, target_language=target,
            metadata={"mode": "preview", "field": "option", "position": index},
        )
        translated_options.append({"position": index, "label": label})

    return {
        "status": "translated",
        "source_language": source,
        "target_language": target,
        "translation": {"title": title, "description": description},
        "options": translated_options,
    }


@router.post("/discord/guilds/{guild_id}/plugins/voting/polls/{poll_id}/translations/{language_code}/generate")
async def generate_translation(guild_id: int, poll_id: UUID, language_code: str,
                               payload: TranslationGenerate,
                               current_user: User = Depends(get_current_user),
                               session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    poll = await get_poll_row(session, guild_id, poll_id)
    source = payload.source_language or poll.primary_language

    source_translation = (await session.execute(select(VotingPollTranslation).where(
        VotingPollTranslation.poll_id == poll.id,
        VotingPollTranslation.language_code == source
    ))).scalar_one_or_none()
    if not source_translation:
        raise HTTPException(422, "Source translation not found.")

    options = list((await session.execute(
        select(VotingOption).where(VotingOption.poll_id == poll.id).order_by(VotingOption.position)
    )).scalars())
    option_ids = [x.id for x in options]
    source_option_rows = list((await session.execute(
        select(VotingOptionTranslation).where(
            VotingOptionTranslation.option_id.in_(option_ids or [UUID(int=0)]),
            VotingOptionTranslation.language_code == source,
        )
    )).scalars())
    source_by_option = {x.option_id: x for x in source_option_rows}

    runtime = AIRuntimeService(session)
    title = await runtime.translate(
        guild_id=guild_id, module_key="voting",
        text=source_translation.title, source_language=source,
        target_language=language_code,
        metadata={"poll_id": str(poll.id), "field": "title"},
    )
    description = None
    if source_translation.description:
        description = await runtime.translate(
            guild_id=guild_id, module_key="voting",
            text=source_translation.description, source_language=source,
            target_language=language_code,
            metadata={"poll_id": str(poll.id), "field": "description"},
        )

    target_poll_translation = (await session.execute(select(VotingPollTranslation).where(
        VotingPollTranslation.poll_id == poll.id,
        VotingPollTranslation.language_code == language_code
    ))).scalar_one_or_none()
    if target_poll_translation and not payload.overwrite_existing:
        raise HTTPException(409, "Translation already exists.")
    if target_poll_translation is None:
        target_poll_translation = VotingPollTranslation(
            poll_id=poll.id, language_code=language_code, title=title
        )
        session.add(target_poll_translation)
    target_poll_translation.title = title
    target_poll_translation.description = description
    target_poll_translation.translation_source = "ai"
    target_poll_translation.reviewed = False
    target_poll_translation.translated_at = datetime.now(UTC)

    translated_options = []
    for option in options:
        source_row = source_by_option.get(option.id)
        if not source_row:
            raise HTTPException(422, f"Source option {option.position + 1} is missing.")
        label = await runtime.translate(
            guild_id=guild_id, module_key="voting",
            text=source_row.label, source_language=source,
            target_language=language_code,
            metadata={"poll_id": str(poll.id), "field": "option", "position": option.position},
        )
        target_row = (await session.execute(select(VotingOptionTranslation).where(
            VotingOptionTranslation.option_id == option.id,
            VotingOptionTranslation.language_code == language_code
        ))).scalar_one_or_none()
        if target_row is None:
            target_row = VotingOptionTranslation(
                option_id=option.id, language_code=language_code, label=label
            )
            session.add(target_row)
        else:
            target_row.label = label
        translated_options.append({"option_id": str(option.id), "label": label})

    if poll.message_id:
        session.add(VotingPublicationJob(poll_id=poll.id, action="refresh"))
    await session.commit()
    return {
        "status": "translated",
        "source_language": source,
        "target_language": language_code,
        "translation": {"title": title, "description": description},
        "options": translated_options,
    }
