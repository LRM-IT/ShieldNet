from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import User
from app.models.template_bank import MediaTemplate
from app.services.global_access import GlobalAccessService
from app.services.template_renderer import TemplateRenderer

router = APIRouter(tags=["Template Renderer"])


class RenderPreviewIn(BaseModel):
    data: dict = Field(default_factory=dict)


def require_superadmin(user: User) -> None:
    GlobalAccessService.require_superadmin(user)


@router.post("/platform/template-bank/templates/{template_id}/render-preview")
async def render_preview(
    template_id: UUID,
    payload: RenderPreviewIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    require_superadmin(current_user)
    template = await session.get(MediaTemplate, template_id)
    if not template:
        raise HTTPException(404, "Template not found.")

    sample = {
        "TITLE": "NAP POLICY VOTING RESULTS",
        "DESCRIPTION": "Thank you for participating!",
        "TOTAL_VOTES": "128",
        "WINNER_LABEL": "NAP 15",
        "WINNER_VOTES": "72",
        "WINNER_PERCENTAGE": "56.3%",
        "OPTION_POSITION": "1",
        "OPTION_LABEL": "NAP 15",
        "OPTION_VOTES": "72",
        "OPTION_PERCENTAGE": "56.3",
        "SERVER_NAME": "Server 2279",
        "RANK_TITLE": "POWER RANKING",
        "RANK_PERIOD": "Season 1",
        "ENTRY_POSITION": "1",
        "ENTRY_NAME": "Player name",
        "ENTRY_VALUE": "245.8M",
        "QR_URL": "https://discord.lrm-it.com",
        "QR_CAPTION": "Visit our website",
    }
    sample.update(payload.data or {})

    output = await TemplateRenderer(session).render(template, sample)
    return Response(
        content=output.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{template.key}-preview.png"'},
    )
