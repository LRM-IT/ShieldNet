from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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

router = APIRouter(tags=["Voting Plugin"])


class OptionIn(BaseModel):
    emoji: str | None = None
    translations: dict[str, str]


class PollCreate(BaseModel):
    primary_language: str = "en"
    fallback_language: str = "en"
    language_selection_mode: str = "automatic_with_selector"
    channel_id: int | None = None
    selection_mode: str = "single"
    anonymous: bool = True
    allow_change_vote: bool = True
    show_live_results: bool = True
    min_choices: int = 1
    max_choices: int = 1
    allowed_role_ids: list[int] = Field(default_factory=list)
    closes_at: datetime | None = None
    translations: dict[str, dict[str, str | None]]
    options: list[OptionIn]


class TranslationGenerate(BaseModel):
    source_language: str | None = None
    overwrite_existing: bool = False
    provider: str = "server_default"


async def serialize_poll(session: AsyncSession, poll: VotingPoll):
    translations = list((await session.execute(
        select(VotingPollTranslation).where(VotingPollTranslation.poll_id == poll.id)
    )).scalars())
    options = list((await session.execute(
        select(VotingOption).where(VotingOption.poll_id == poll.id)
        .order_by(VotingOption.position)
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
        "id": str(poll.id), "guild_id": poll.guild_id, "status": poll.status,
        "channel_id": poll.channel_id, "message_id": poll.message_id,
        "primary_language": poll.primary_language,
        "fallback_language": poll.fallback_language,
        "language_selection_mode": poll.language_selection_mode,
        "selection_mode": poll.selection_mode, "anonymous": poll.anonymous,
        "allow_change_vote": poll.allow_change_vote,
        "show_live_results": poll.show_live_results,
        "min_choices": poll.min_choices, "max_choices": poll.max_choices,
        "allowed_role_ids": poll.allowed_role_ids or [],
        "closes_at": poll.closes_at,
        "translations": {
            t.language_code: {
                "title": t.title, "description": t.description,
                "completion_message": t.completion_message,
                "source": t.translation_source, "reviewed": t.reviewed,
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
    if not 2 <= len(payload.options) <= 10:
        raise HTTPException(422, "A poll must contain 2-10 options.")
    if payload.primary_language not in payload.translations:
        raise HTTPException(422, "Primary language translation is required.")
    poll = VotingPoll(
        guild_id=guild_id, created_by_user_id=getattr(current_user, "id", None),
        primary_language=payload.primary_language,
        fallback_language=payload.fallback_language,
        language_selection_mode=payload.language_selection_mode,
        channel_id=payload.channel_id, selection_mode=payload.selection_mode,
        anonymous=payload.anonymous, allow_change_vote=payload.allow_change_vote,
        show_live_results=payload.show_live_results,
        min_choices=payload.min_choices, max_choices=payload.max_choices,
        allowed_role_ids=payload.allowed_role_ids, closes_at=payload.closes_at,
    )
    session.add(poll)
    await session.flush()
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
            session.add(VotingOptionTranslation(
                option_id=option.id, language_code=language, label=label
            ))
    await session.commit()
    await session.refresh(poll)
    return await serialize_poll(session, poll)


@router.get("/discord/guilds/{guild_id}/plugins/voting/polls/{poll_id}")
async def get_poll(guild_id: int, poll_id: UUID,
                   current_user: User = Depends(get_current_user),
                   session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    poll = (await session.execute(select(VotingPoll).where(
        VotingPoll.id == poll_id, VotingPoll.guild_id == guild_id
    ))).scalar_one_or_none()
    if not poll:
        raise HTTPException(404, "Poll not found.")
    return await serialize_poll(session, poll)


@router.post("/discord/guilds/{guild_id}/plugins/voting/polls/{poll_id}/publish")
async def publish_poll(guild_id: int, poll_id: UUID,
                       current_user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    poll = (await session.execute(select(VotingPoll).where(
        VotingPoll.id == poll_id, VotingPoll.guild_id == guild_id
    ))).scalar_one_or_none()
    if not poll:
        raise HTTPException(404, "Poll not found.")
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
    poll = (await session.execute(select(VotingPoll).where(
        VotingPoll.id == poll_id, VotingPoll.guild_id == guild_id
    ))).scalar_one_or_none()
    if not poll:
        raise HTTPException(404, "Poll not found.")
    poll.status = "closed"
    poll.closed_at = datetime.now(UTC)
    session.add(VotingPublicationJob(poll_id=poll.id, action="refresh"))
    await session.commit()
    return {"status": "closed"}


@router.post("/discord/guilds/{guild_id}/plugins/voting/polls/{poll_id}/translations/{language_code}/generate")
async def generate_translation(guild_id: int, poll_id: UUID, language_code: str,
                               payload: TranslationGenerate,
                               current_user: User = Depends(get_current_user),
                               session: AsyncSession = Depends(get_db_session)):
    await require_guild_management(session, current_user, guild_id)
    poll = (await session.execute(select(VotingPoll).where(
        VotingPoll.id == poll_id, VotingPoll.guild_id == guild_id
    ))).scalar_one_or_none()
    if not poll:
        raise HTTPException(404, "Poll not found.")
    # Uses the existing ShieldNet AI gateway. The exact provider route is kept
    # isolated so deployments can connect their current AI service here.
    source = payload.source_language or poll.primary_language
    source_translation = (await session.execute(select(VotingPollTranslation).where(
        VotingPollTranslation.poll_id == poll.id,
        VotingPollTranslation.language_code == source
    ))).scalar_one_or_none()
    if not source_translation:
        raise HTTPException(422, "Source translation not found.")
    return {
        "status": "translation_required",
        "source_language": source,
        "target_language": language_code,
        "provider": payload.provider,
        "source": {
            "title": source_translation.title,
            "description": source_translation.description,
        },
        "message": "Connect this request to the configured ShieldNet AI gateway.",
    }
