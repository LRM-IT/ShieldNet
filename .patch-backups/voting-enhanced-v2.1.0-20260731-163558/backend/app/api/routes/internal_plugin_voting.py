from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.internal import verify_internal_service_token
from app.db.session import get_db_session
from app.models.plugin_voting import (
    VotingOption, VotingPoll, VotingPublicationJob, VotingVote
)
from app.api.routes.plugin_voting import serialize_poll

router = APIRouter(
    prefix="/internal/discord/plugins/voting",
    tags=["Internal Voting"],
    dependencies=[Depends(verify_internal_service_token)],
)


class VoteIn(BaseModel):
    option_id: UUID
    discord_user_id: int
    language_code: str | None = None


class CompleteIn(BaseModel):
    message_id: int


class FailIn(BaseModel):
    error: str


@router.get("/jobs")
async def jobs(session: AsyncSession = Depends(get_db_session)):
    rows = list((await session.execute(
        select(VotingPublicationJob)
        .where(VotingPublicationJob.status == "pending")
        .order_by(VotingPublicationJob.created_at)
        .limit(20)
    )).scalars())
    result = []
    for job in rows:
        poll = (await session.execute(
            select(VotingPoll).where(VotingPoll.id == job.poll_id)
        )).scalar_one()
        job.status = "processing"
        result.append({
            "id": job.id, "action": job.action,
            "poll": await serialize_poll(session, poll)
        })
    await session.commit()
    return {"items": result}


@router.post("/{poll_id}/vote")
async def vote(poll_id: UUID, payload: VoteIn,
               session: AsyncSession = Depends(get_db_session)):
    poll = (await session.execute(
        select(VotingPoll).where(VotingPoll.id == poll_id)
    )).scalar_one_or_none()
    if not poll or poll.status != "active":
        raise HTTPException(409, "Voting is not active.")
    option = (await session.execute(select(VotingOption).where(
        VotingOption.id == payload.option_id, VotingOption.poll_id == poll.id
    ))).scalar_one_or_none()
    if not option:
        raise HTTPException(422, "Voting option not found.")
    if poll.allow_change_vote and poll.selection_mode == "single":
        await session.execute(delete(VotingVote).where(
            VotingVote.poll_id == poll.id,
            VotingVote.discord_user_id == payload.discord_user_id
        ))
    existing = (await session.execute(select(VotingVote).where(
        VotingVote.poll_id == poll.id,
        VotingVote.option_id == option.id,
        VotingVote.discord_user_id == payload.discord_user_id
    ))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "You already selected this option.")
    session.add(VotingVote(
        poll_id=poll.id, option_id=option.id,
        discord_user_id=payload.discord_user_id,
        language_code=payload.language_code
    ))
    session.add(VotingPublicationJob(poll_id=poll.id, action="refresh"))
    await session.commit()
    return {"status": "recorded", "message": "Your vote was recorded."}


@router.post("/jobs/{job_id}/complete")
async def complete(job_id: int, payload: CompleteIn,
                   session: AsyncSession = Depends(get_db_session)):
    job = (await session.execute(select(VotingPublicationJob).where(
        VotingPublicationJob.id == job_id
    ))).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found.")
    poll = (await session.execute(select(VotingPoll).where(
        VotingPoll.id == job.poll_id
    ))).scalar_one()
    poll.message_id = payload.message_id
    if job.action == "publish":
        poll.status = "active"
        poll.published_at = datetime.now(UTC)
    job.status = "completed"
    job.processed_at = datetime.now(UTC)
    await session.commit()
    return {"status": "completed"}


@router.post("/jobs/{job_id}/failed")
async def failed(job_id: int, payload: FailIn,
                 session: AsyncSession = Depends(get_db_session)):
    job = (await session.execute(select(VotingPublicationJob).where(
        VotingPublicationJob.id == job_id
    ))).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found.")
    job.status = "failed"
    job.error = payload.error
    job.processed_at = datetime.now(UTC)
    await session.commit()
    return {"status": "failed"}
