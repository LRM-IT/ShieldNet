from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.internal import verify_internal_service_token
from app.api.routes.plugin_voting import serialize_poll
from app.db.session import get_db_session
from app.models.plugin_voting import VotingPoll
from app.services.voting_template_result import render_voting_result

router = APIRouter(
    prefix="/internal/discord/plugins/voting",
    tags=["Internal Voting Result Renderer"],
    dependencies=[Depends(verify_internal_service_token)],
)


@router.get("/{poll_id}/result-image")
async def result_image(
    poll_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    poll = (
        await session.execute(select(VotingPoll).where(VotingPoll.id == poll_id))
    ).scalar_one_or_none()
    if poll is None:
        raise HTTPException(404, "Poll not found.")

    serialized = await serialize_poll(session, poll)
    content = await render_voting_result(session, poll, serialized)
    if content is None:
        raise HTTPException(404, "No active voting result template is available.")

    return Response(
        content=content,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="poll-{poll.id}-results.png"'
        },
    )
