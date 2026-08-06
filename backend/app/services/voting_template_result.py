from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plugin_voting import VotingPoll
from app.models.template_bank import MediaTemplate, TemplateBankSettings
from app.services.template_renderer import TemplateRenderer


async def resolve_voting_template(session: AsyncSession, poll: VotingPoll) -> MediaTemplate | None:
    if poll.result_template_id:
        template = await session.get(MediaTemplate, poll.result_template_id)
        if template and template.is_active and template.category == "voting":
            return template

    return (
        await session.execute(
            select(MediaTemplate)
            .where(
                MediaTemplate.category == "voting",
                MediaTemplate.is_active.is_(True),
                MediaTemplate.is_default.is_(True),
            )
            .order_by(MediaTemplate.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def build_voting_render_data(poll: dict[str, Any], language: str) -> dict[str, Any]:
    translations = poll.get("translations") or {}
    text = (
        translations.get(language)
        or translations.get(poll.get("fallback_language"))
        or translations.get(poll.get("primary_language"))
        or {}
    )
    options = list(poll.get("options") or [])
    total = sum(int(option.get("votes") or 0) for option in options)
    winner = max(options, key=lambda item: int(item.get("votes") or 0), default=None)
    winner_votes = int((winner or {}).get("votes") or 0)
    winner_translation = (
        (winner or {}).get("translations", {}).get(language)
        or (winner or {}).get("translations", {}).get(poll.get("primary_language"))
        or {}
    )
    winner_percentage = (winner_votes / total * 100) if total else 0.0
    settings = poll.get("result_settings") or {}

    data = {
        "TITLE": text.get("title") or "Voting results",
        "DESCRIPTION": text.get("description") or "",
        "TOTAL_VOTES": total,
        "WINNER_LABEL": winner_translation.get("label") or "",
        "WINNER_VOTES": winner_votes,
        "WINNER_PERCENTAGE": f"{winner_percentage:.1f}",
        "SERVER_NAME": settings.get("server_name") or f"Server {poll.get('guild_id', '')}",
        "GAME_NAME": settings.get("game_name") or "",
        "QR_URL": poll.get("result_qr_url") or settings.get("qr_url") or "",
        "QR_CAPTION": settings.get("qr_caption") or "Visit our website",
        "DATE": str(poll.get("closed_at") or "")[:10],
        "OPTIONS": [],
    }

    for index, option in enumerate(options[:10], start=1):
        option_text = (
            option.get("translations", {}).get(language)
            or option.get("translations", {}).get(poll.get("primary_language"))
            or {}
        )
        votes = int(option.get("votes") or 0)
        percentage = (votes / total * 100) if total else 0.0
        data[f"OPTION_{index}_POSITION"] = index
        data[f"OPTION_{index}_LABEL"] = option_text.get("label") or f"Option {index}"
        data[f"OPTION_{index}_VOTES"] = votes
        data[f"OPTION_{index}_PERCENTAGE"] = f"{percentage:.1f}"
        data["OPTIONS"].append({
            "POSITION": index,
            "LABEL": option_text.get("label") or f"Option {index}",
            "VOTES": votes,
            "PERCENTAGE": f"{percentage:.1f}",
            "IS_WINNER": votes == winner_votes and winner_votes > 0,
        })

    return data


async def render_voting_result(
    session: AsyncSession,
    poll_row: VotingPoll,
    serialized_poll: dict[str, Any],
) -> bytes | None:
    if not poll_row.publish_result_image:
        return None

    template = await resolve_voting_template(session, poll_row)
    if template is None:
        return None

    language = poll_row.result_language or poll_row.primary_language or "en"
    data = build_voting_render_data(serialized_poll, language)

    settings = await session.get(TemplateBankSettings, 1)
    if not data["QR_URL"]:
        data["QR_URL"] = settings.default_qr_url if settings else "https://discord.lrm-it.com"
    if settings and not data["QR_CAPTION"]:
        data["QR_CAPTION"] = settings.default_qr_caption

    rendered = await TemplateRenderer(session).render(template, data)
    return rendered.getvalue()
