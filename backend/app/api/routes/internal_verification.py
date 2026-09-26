import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.internal import (
    verify_internal_service_token,
)
from app.db.session import get_db_session
from app.models.verification import (
    VerificationRequest,
    VerificationSettings,
)
from app.schemas.verification import (
    VerificationRequestCreate,
    VerificationRequestResult,
)

class DiscordVerificationDecision(BaseModel):
    moderator_discord_user_id: int
    reason: str | None = Field(default=None, max_length=1000)


router = APIRouter(
    prefix="/internal/verification",
    tags=["Internal Verification"],
    dependencies=[Depends(verify_internal_service_token)],
)


@router.get("/guilds/{guild_id}/settings")
async def internal_settings(guild_id: int, session: AsyncSession = Depends(get_db_session)):
    item = await session.scalar(select(VerificationSettings).where(VerificationSettings.guild_id == guild_id))
    if item is None:
        return {"enabled": False, "invocation_channel_id": None, "text_commands": "", "slash_command_name": "verify", "channel_cleanup_minutes": 0, "auto_approve": True, "review_channel_id": None}
    return {"enabled": item.enabled, "invocation_channel_id": str(item.invocation_channel_id) if item.invocation_channel_id else None,
            "text_commands": item.text_commands, "slash_command_name": item.slash_command_name,
            "channel_cleanup_minutes": item.channel_cleanup_minutes, "auto_approve": item.auto_approve,
            "review_channel_id": str(item.review_channel_id) if item.review_channel_id else None}


@router.post("/guilds/{guild_id}/requests")
async def create_request(
    guild_id: int,
    payload: VerificationRequestCreate,
    session: AsyncSession = Depends(get_db_session),
):
    settings = (
        await session.execute(
            select(VerificationSettings).where(
                VerificationSettings.guild_id == guild_id
            )
        )
    ).scalar_one_or_none()

    if settings is None or not settings.enabled:
        raise HTTPException(
            status_code=409,
            detail="Verification module is disabled.",
        )

    alliance = payload.alliance.strip().upper()
    nickname = payload.nickname.strip()
    server_number = payload.server_number.strip()

    if not (
        settings.alliance_min_length
        <= len(alliance)
        <= settings.alliance_max_length
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Alliance length must be between "
                f"{settings.alliance_min_length} and "
                f"{settings.alliance_max_length} characters."
            ),
        )

    try:
        requested_nickname = settings.nickname_template.format(
            alliance=alliance,
            nickname=nickname,
            server=server_number,
        )[:32]
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Invalid nickname template.",
        ) from exc

    item = VerificationRequest(
        guild_id=guild_id,
        discord_user_id=payload.discord_user_id,
        alliance=alliance,
        nickname=nickname,
        server_number=server_number,
        requested_nickname=requested_nickname,
        status="approved" if settings.auto_approve else "pending",
        decided_at=datetime.now(UTC) if settings.auto_approve else None,
    )
    session.add(item)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "You already have an active "
                "verification request."
            ),
        ) from exc

    await session.refresh(item)

    return {
        "id": str(item.id),
        "guild_id": item.guild_id,
        "discord_user_id": item.discord_user_id,
        "alliance": item.alliance,
        "nickname": item.nickname,
        "server_number": item.server_number,
        "requested_nickname": item.requested_nickname,
        "status": item.status,
    }


@router.get("/guilds/{guild_id}/requests/pending")
async def approved_for_execution(
    guild_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    settings = (
        await session.execute(
            select(VerificationSettings).where(
                VerificationSettings.guild_id == guild_id
            )
        )
    ).scalar_one_or_none()

    result = await session.execute(
        select(VerificationRequest)
        .where(
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.status == "approved",
        )
        .order_by(VerificationRequest.created_at)
        .limit(50)
        .with_for_update(skip_locked=True)
    )

    items = list(result.scalars().all())

    for item in items:
        item.status = "processing"
        item.updated_at = datetime.now(UTC)

    await session.commit()

    return {
        "items": [
            {
                "id": str(item.id),
                "discord_user_id": item.discord_user_id,
                "requested_nickname": item.requested_nickname,
                "verified_role_id": (
                    settings.verified_role_id
                    if settings is not None
                    else None
                ),
            }
            for item in items
        ]
    }


@router.post("/requests/{request_id}/result")
async def save_result(
    request_id: uuid.UUID,
    payload: VerificationRequestResult,
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.status == "processing",
        )
        .values(
            status=payload.status,
            result_message=payload.result_message,
            last_error=(payload.result_message if payload.status == "failed" else None),
            processed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        .returning(VerificationRequest.id)
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=409,
            detail="Request is not processing.",
        )

    await session.commit()
    return {"status": "saved"}

@router.get("/guilds/{guild_id}/notifications")
async def pending_notifications(
    guild_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(VerificationRequest)
        .where(
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.notification_status == "pending",
        )
        .order_by(VerificationRequest.created_at)
        .limit(50)
        .with_for_update(skip_locked=True)
    )

    items = list(result.scalars().all())

    for item in items:
        item.notification_status = "processing"

    await session.commit()

    return {
        "items": [
            {
                "id": str(item.id),
                "discord_user_id": item.discord_user_id,
                "status": item.status,
                "message": item.notification_message,
            }
            for item in items
        ]
    }


@router.post("/notifications/{request_id}/result")
async def notification_result(
    request_id: uuid.UUID,
    payload: VerificationRequestResult,
    session: AsyncSession = Depends(get_db_session),
):
    delivered = payload.status == "completed"

    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.notification_status == "processing",
        )
        .values(
            notification_status="sent" if delivered else "failed",
            notified_at=datetime.now(UTC) if delivered else None,
        )
        .returning(VerificationRequest.id)
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=409,
            detail="Notification is not processing.",
        )

    await session.commit()
    return {"status": "saved"}


@router.get("/guilds/{guild_id}/review-notifications")
async def pending_review_notifications(
    guild_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    settings = (
        await session.execute(
            select(VerificationSettings).where(
                VerificationSettings.guild_id == guild_id
            )
        )
    ).scalar_one_or_none()

    if settings is None or not settings.review_channel_id:
        return {"channel_id": None, "items": []}

    result = await session.execute(
        select(VerificationRequest)
        .where(
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.status == "pending",
            VerificationRequest.review_notification_status == "pending",
        )
        .order_by(VerificationRequest.created_at)
        .limit(50)
        .with_for_update(skip_locked=True)
    )
    items = list(result.scalars().all())

    for item in items:
        item.review_notification_status = "processing"

    await session.commit()

    return {
        "channel_id": settings.review_channel_id,
        "items": [
            {
                "id": str(item.id),
                "discord_user_id": item.discord_user_id,
                "alliance": item.alliance,
                "nickname": item.nickname,
                "server_number": item.server_number,
                "requested_nickname": item.requested_nickname,
            }
            for item in items
        ],
    }


@router.post("/review-notifications/{request_id}/result")
async def review_notification_result(
    request_id: uuid.UUID,
    payload: VerificationRequestResult,
    session: AsyncSession = Depends(get_db_session),
):
    delivered = payload.status == "completed"
    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.review_notification_status == "processing",
        )
        .values(
            review_notification_status="sent" if delivered else "failed",
            review_notified_at=datetime.now(UTC) if delivered else None,
        )
        .returning(VerificationRequest.id)
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=409,
            detail="Review notification is not processing.",
        )

    await session.commit()
    return {"status": "saved"}


@router.get("/guilds/{guild_id}/users/{discord_user_id}/latest")
async def latest_user_request(
    guild_id: int,
    discord_user_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    item = (
        await session.execute(
            select(VerificationRequest)
            .where(
                VerificationRequest.guild_id == guild_id,
                VerificationRequest.discord_user_id == discord_user_id,
            )
            .order_by(VerificationRequest.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if item is None:
        return {"request": None}

    return {"request": {
        "id": str(item.id),
        "requested_nickname": item.requested_nickname,
        "status": item.status,
        "result_message": item.result_message,
        "decision_reason": item.decision_reason,
    }}


@router.post("/requests/{request_id}/discord-approve")
async def discord_approve_request(
    request_id: uuid.UUID,
    payload: DiscordVerificationDecision,
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.status == "pending",
        )
        .values(
            status="approved",
            decided_by_discord_user_id=payload.moderator_discord_user_id,
            decided_at=datetime.now(UTC),
        )
        .returning(VerificationRequest.id)
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=409, detail="Request is not pending.")

    await session.commit()
    return {"status": "approved"}


@router.post("/requests/{request_id}/discord-reject")
async def discord_reject_request(
    request_id: uuid.UUID,
    payload: DiscordVerificationDecision,
    session: AsyncSession = Depends(get_db_session),
):
    reason = (payload.reason or "").strip()

    if not reason:
        raise HTTPException(
            status_code=400,
            detail="Rejection reason is required.",
        )

    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.status == "pending",
        )
        .values(
            status="rejected",
            decided_by_discord_user_id=payload.moderator_discord_user_id,
            decision_reason=reason,
            result_message=reason,
            decided_at=datetime.now(UTC),
            processed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            notification_status="pending",
            notification_message=reason,
        )
        .returning(VerificationRequest.id)
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=409, detail="Request is not pending.")

    await session.commit()
    return {"status": "rejected"}
