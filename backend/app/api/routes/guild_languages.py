from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import require_guild_module
from app.db.session import get_db_session
from app.models.core import User
from app.models.global_languages import GlobalLanguage
from app.models.guild_languages import GuildLanguage

router = APIRouter(tags=["Guild Languages"])


class GuildLanguageItem(BaseModel):
    code: str = Field(min_length=2, max_length=16)
    enabled: bool = True
    is_primary: bool = False
    is_fallback: bool = False
    sort_order: int = Field(default=100, ge=0, le=10000)


class GuildLanguageUpdate(BaseModel):
    items: list[GuildLanguageItem]


def serialize(
    language: GlobalLanguage,
    selected: GuildLanguage | None,
) -> dict:
    return {
        "id": language.id,
        "code": language.code,
        "name": language.name,
        "native_name": language.native_name,
        "flag": language.flag,
        "locale": language.locale,
        "is_active": language.is_active,
        "selected": selected is not None,
        "enabled": selected.enabled if selected else False,
        "is_primary": selected.is_primary if selected else False,
        "is_fallback": selected.is_fallback if selected else False,
        "sort_order": (
            selected.sort_order if selected else language.sort_order
        ),
    }


async def full_catalogue(
    session: AsyncSession,
    guild_id: int,
) -> list[dict]:
    rows = (
        await session.execute(
            select(GlobalLanguage, GuildLanguage)
            .outerjoin(
                GuildLanguage,
                (GuildLanguage.language_code == GlobalLanguage.code)
                & (GuildLanguage.guild_id == guild_id),
            )
            .where(GlobalLanguage.is_active.is_(True))
            .order_by(
                GuildLanguage.sort_order.nulls_last(),
                GlobalLanguage.sort_order,
                GlobalLanguage.name,
            )
        )
    ).all()

    return [
        serialize(language, selected)
        for language, selected in rows
    ]


@router.get("/discord/guilds/{guild_id}/languages")
async def list_guild_languages(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    await require_guild_module(
        session,
        current_user,
        guild_id,
        "settings",
    )
    return await full_catalogue(session, guild_id)


@router.put("/discord/guilds/{guild_id}/languages")
async def replace_guild_languages(
    guild_id: int,
    payload: GuildLanguageUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    await require_guild_module(
        session,
        current_user,
        guild_id,
        "settings",
    )

    active_codes = set(
        (
            await session.execute(
                select(GlobalLanguage.code).where(
                    GlobalLanguage.is_active.is_(True)
                )
            )
        ).scalars()
    )

    codes = [item.code for item in payload.items]

    if len(codes) != len(set(codes)):
        raise HTTPException(
            status_code=422,
            detail="A language may only be selected once.",
        )

    invalid = sorted(set(codes) - active_codes)
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=(
                "Unknown or inactive languages: "
                + ", ".join(invalid)
            ),
        )

    enabled_items = [
        item for item in payload.items if item.enabled
    ]

    if not enabled_items:
        raise HTTPException(
            status_code=422,
            detail="Select at least one enabled language.",
        )

    if sum(item.is_primary for item in enabled_items) != 1:
        raise HTTPException(
            status_code=422,
            detail="Select exactly one primary language.",
        )

    if sum(item.is_fallback for item in enabled_items) != 1:
        raise HTTPException(
            status_code=422,
            detail="Select exactly one fallback language.",
        )

    await session.execute(
        delete(GuildLanguage).where(
            GuildLanguage.guild_id == guild_id
        )
    )

    for item in payload.items:
        session.add(
            GuildLanguage(
                guild_id=guild_id,
                language_code=item.code,
                enabled=item.enabled,
                is_primary=item.is_primary,
                is_fallback=item.is_fallback,
                sort_order=item.sort_order,
            )
        )

    await session.commit()
    return await full_catalogue(session, guild_id)


@router.get(
    "/discord/guilds/{guild_id}/available-languages"
)
async def available_guild_languages(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    await require_guild_module(
        session,
        current_user,
        guild_id,
        "settings",
    )

    rows = (
        await session.execute(
            select(GlobalLanguage, GuildLanguage)
            .join(
                GuildLanguage,
                (
                    GuildLanguage.language_code
                    == GlobalLanguage.code
                )
                & (GuildLanguage.guild_id == guild_id),
            )
            .where(
                GlobalLanguage.is_active.is_(True),
                GuildLanguage.enabled.is_(True),
            )
            .order_by(
                GuildLanguage.sort_order,
                GlobalLanguage.name,
            )
        )
    ).all()

    if rows:
        return [
            serialize(language, selected)
            for language, selected in rows
        ]

    # Initial safe fallback. Plugin forms never receive the full catalogue.
    fallback_languages = (
        await session.execute(
            select(GlobalLanguage)
            .where(
                GlobalLanguage.is_active.is_(True),
                GlobalLanguage.code.in_(("en", "uk")),
            )
            .order_by(
                GlobalLanguage.sort_order,
                GlobalLanguage.name,
            )
        )
    ).scalars().all()

    if not fallback_languages:
        first_language = await session.scalar(
            select(GlobalLanguage)
            .where(GlobalLanguage.is_active.is_(True))
            .order_by(
                GlobalLanguage.sort_order,
                GlobalLanguage.name,
            )
            .limit(1)
        )
        fallback_languages = (
            [first_language] if first_language else []
        )

    primary_code = (
        "en"
        if any(item.code == "en" for item in fallback_languages)
        else (
            fallback_languages[0].code
            if fallback_languages
            else None
        )
    )

    return [
        {
            **serialize(language, None),
            "selected": True,
            "enabled": True,
            "is_primary": language.code == primary_code,
            "is_fallback": language.code == primary_code,
        }
        for language in fallback_languages
    ]
