import csv
import io
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.guild_access import (
    require_guild_management,
)
from app.db.session import get_db_session
from app.models.core import User
from app.models.verification import (
    VerificationDecision,
    VerificationRequest,
    VerificationSettings,
)
from app.schemas.verification import (
    VerificationBulkInput,
    VerificationChangesInput,
    VerificationDecisionInput,
    VerificationResubmitInput,
    VerificationRecoverInput,
    VerificationSettingsInput,
)
from app.services.audit_service import AuditService

router = APIRouter(tags=["Verification"])


def serialize_request(item: VerificationRequest) -> dict:
    return {
        "id": str(item.id),
        "guild_id": item.guild_id,
        "discord_user_id": item.discord_user_id,
        "alliance": item.alliance,
        "nickname": item.nickname,
        "server_number": item.server_number,
        "requested_nickname": item.requested_nickname,
        "status": item.status,
        "result_message": item.result_message,
        "retry_count": item.retry_count,
        "last_error": item.last_error,
        "decision_reason": item.decision_reason,
        "decided_at": item.decided_at,
        "processed_at": item.processed_at,
        "evidence_url": item.evidence_url,
        "submitted_language": item.submitted_language,
        "applicant_comment": item.applicant_comment,
        "change_request_reason": item.change_request_reason,
        "revision_count": item.revision_count,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get(
    "/discord/guilds/{guild_id}/verification/settings"
)
async def get_settings(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    item = (
        await session.execute(
            select(VerificationSettings).where(
                VerificationSettings.guild_id == guild_id
            )
        )
    ).scalar_one_or_none()

    if item is None:
        item = VerificationSettings(
            guild_id=guild_id,
            auto_approve=False,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)

    return {
        "guild_id": guild_id,
        "enabled": item.enabled,
        "verified_role_id": item.verified_role_id,
        "review_channel_id": item.review_channel_id,
        "invocation_channel_id": item.invocation_channel_id,
        "text_commands": item.text_commands,
        "nickname_template": item.nickname_template,
        "auto_approve": item.auto_approve,
        "alliance_min_length": item.alliance_min_length,
        "alliance_max_length": item.alliance_max_length,
    }


@router.put(
    "/discord/guilds/{guild_id}/verification/settings"
)
async def save_settings(
    guild_id: int,
    payload: VerificationSettingsInput,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    item = (
        await session.execute(
            select(VerificationSettings).where(
                VerificationSettings.guild_id == guild_id
            )
        )
    ).scalar_one_or_none()

    if item is None:
        item = VerificationSettings(guild_id=guild_id)
        session.add(item)

    for key, value in payload.model_dump().items():
        setattr(item, key, value)

    item.updated_by = current_user.id
    item.updated_at = datetime.now(UTC)

    await AuditService(session).record(
        guild_id=guild_id,
        actor_user_id=current_user.id,
        event_type="verification.settings_update",
        target_type="verification_settings",
        target_id=str(guild_id),
        payload=payload.model_dump(mode="json"),
        result="saved",
    )

    await session.commit()
    return {"status": "saved"}


@router.get(
    "/discord/guilds/{guild_id}/verification/requests"
)
async def list_requests(
    guild_id: int,
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    query = (
        select(VerificationRequest)
        .where(VerificationRequest.guild_id == guild_id)
        .order_by(VerificationRequest.created_at.desc())
        .limit(200)
    )

    if status_filter:
        query = query.where(
            VerificationRequest.status == status_filter
        )

    if search:
        value = search.strip()
        conditions = [
            VerificationRequest.alliance.ilike(f"%{value}%"),
            VerificationRequest.nickname.ilike(f"%{value}%"),
            VerificationRequest.requested_nickname.ilike(f"%{value}%"),
        ]

        if value.isdigit():
            conditions.append(
                VerificationRequest.discord_user_id == int(value)
            )

        query = query.where(or_(*conditions))

    result = await session.execute(query)

    return {
        "items": [
            serialize_request(item)
            for item in result.scalars().all()
        ]
    }


@router.post(
    "/discord/guilds/{guild_id}/verification/"
    "requests/{request_id}/approve"
)
async def approve_request(
    guild_id: int,
    request_id: uuid.UUID,
    payload: VerificationDecisionInput,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.status == "pending",
        )
        .values(
            status="approved",
            decided_by=current_user.id,
            decision_reason=payload.reason,
            decided_at=datetime.now(UTC),
        )
        .returning(VerificationRequest.id)
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=409,
            detail="Request is not pending.",
        )

    await AuditService(session).record(
        guild_id=guild_id,
        actor_user_id=current_user.id,
        event_type="verification.approved",
        target_type="verification_request",
        target_id=str(request_id),
        payload={"reason": payload.reason},
        result="approved",
    )

    await session.commit()
    return {"status": "approved"}


@router.post(
    "/discord/guilds/{guild_id}/verification/"
    "requests/{request_id}/reject"
)
async def reject_request(
    guild_id: int,
    request_id: uuid.UUID,
    payload: VerificationDecisionInput,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

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
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.status == "pending",
        )
        .values(
            status="rejected",
            decided_by=current_user.id,
            decision_reason=reason,
            result_message=reason,
            decided_at=datetime.now(UTC),
            processed_at=datetime.now(UTC),
            notification_status="pending",
            notification_message=reason,
        )
        .returning(VerificationRequest.discord_user_id)
    )

    discord_user_id = result.scalar_one_or_none()

    if discord_user_id is None:
        raise HTTPException(
            status_code=409,
            detail="Request is not pending.",
        )

    await AuditService(session).record(
        guild_id=guild_id,
        actor_user_id=current_user.id,
        event_type="verification.rejected",
        target_type="verification_request",
        target_id=str(request_id),
        payload={
            "reason": reason,
            "discord_user_id": discord_user_id,
        },
        result="rejected",
    )

    await session.commit()

    return {
        "status": "rejected",
        "discord_user_id": discord_user_id,
        "reason": reason,
    }

@router.post(
    "/discord/guilds/{guild_id}/verification/"
    "requests/{request_id}/retry"
)
async def retry_request(
    guild_id: int,
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.status == "failed",
        )
        .values(
            status="approved",
            result_message=None,
            processed_at=None,
            notification_status="none",
            notification_message=None,
            notified_at=None,
        )
        .returning(VerificationRequest.id)
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=409,
            detail="Only failed requests can be retried.",
        )

    await AuditService(session).record(
        guild_id=guild_id,
        actor_user_id=current_user.id,
        event_type="verification.retry",
        target_type="verification_request",
        target_id=str(request_id),
        result="queued",
    )

    await session.commit()
    return {"status": "approved"}


@router.get("/discord/guilds/{guild_id}/verification/summary")
async def verification_summary(
    guild_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(session, current_user, guild_id)
    from sqlalchemy import func
    rows = await session.execute(
        select(VerificationRequest.status, func.count(VerificationRequest.id))
        .where(VerificationRequest.guild_id == guild_id)
        .group_by(VerificationRequest.status)
    )
    counts = dict(rows.all())
    return {
        "total": sum(counts.values()),
        "pending": counts.get("pending", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
        "rejected": counts.get("rejected", 0),
    }

@router.post("/discord/guilds/{guild_id}/verification/requests/{request_id}/cancel")
async def cancel_request(
    guild_id: int,
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(session, current_user, guild_id)
    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.status == "pending",
        )
        .values(status="cancelled", result_message="Cancelled by administrator.", processed_at=datetime.now(UTC))
        .returning(VerificationRequest.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=409, detail="Only pending requests can be cancelled.")
    await session.commit()
    return {"status": "cancelled"}

@router.post("/discord/guilds/{guild_id}/verification/requests/{request_id}/requeue")
async def requeue_request(
    guild_id: int,
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(session, current_user, guild_id)
    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.id == request_id,
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.status.in_(["failed", "processing", "approved"]),
        )
        .values(status="approved", result_message=None, last_error=None, processed_at=None, retry_count=VerificationRequest.retry_count + 1)
        .returning(VerificationRequest.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=409, detail="Request cannot be requeued.")
    await session.commit()
    return {"status": "approved"}

@router.post("/discord/guilds/{guild_id}/verification/requests/{request_id}/resend-review")
async def resend_review(
    guild_id: int,
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(session, current_user, guild_id)
    result = await session.execute(
        update(VerificationRequest)
        .where(VerificationRequest.id == request_id, VerificationRequest.guild_id == guild_id)
        .values(review_notification_status="pending", review_notified_at=None, review_message_id=None)
        .returning(VerificationRequest.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    await session.commit()
    return {"status": "pending"}



@router.post("/discord/guilds/{guild_id}/verification/requests/{request_id}/request-changes")
async def request_verification_changes(
    guild_id: int, request_id: uuid.UUID, payload: VerificationChangesInput,
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(session, current_user, guild_id)
    reason = payload.reason.strip()
    item = (await session.execute(select(VerificationRequest).where(
        VerificationRequest.id == request_id, VerificationRequest.guild_id == guild_id
    ))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    if item.status not in {"pending", "rejected"}:
        raise HTTPException(status_code=409, detail="Changes can only be requested for pending or rejected requests.")
    item.status = "changes_requested"
    item.change_request_reason = reason
    item.decision_reason = reason
    item.decided_by = current_user.id
    item.decided_at = datetime.now(UTC)
    item.notification_status = "pending"
    item.notification_message = reason
    item.updated_at = datetime.now(UTC)
    session.add(VerificationDecision(request_id=item.id, guild_id=guild_id, action="changes_requested", reason=reason, actor_user_id=current_user.id))
    await AuditService(session).record(guild_id=guild_id, actor_user_id=current_user.id, event_type="verification.changes_requested", target_type="verification_request", target_id=str(request_id), payload={"reason": reason}, result="changes_requested")
    await session.commit()
    return {"status": "changes_requested"}


@router.post("/discord/guilds/{guild_id}/verification/requests/{request_id}/resubmit")
async def resubmit_verification_request(
    guild_id: int, request_id: uuid.UUID, payload: VerificationResubmitInput,
    session: AsyncSession = Depends(get_db_session),
):
    item = (await session.execute(select(VerificationRequest).where(
        VerificationRequest.id == request_id, VerificationRequest.guild_id == guild_id
    ))).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    if item.status != "changes_requested":
        raise HTTPException(status_code=409, detail="Request is not awaiting changes.")
    item.alliance = payload.alliance.strip().upper()
    item.nickname = payload.nickname.strip()
    settings = await session.scalar(select(VerificationSettings).where(VerificationSettings.guild_id == guild_id))
    template = settings.nickname_template if settings else "[{alliance}] {nickname}"
    item.requested_nickname = template.format(
        alliance=item.alliance, nickname=item.nickname, server=item.server_number,
    )[:32]
    item.evidence_url = payload.evidence_url
    item.submitted_language = payload.submitted_language.lower() if payload.submitted_language else None
    item.applicant_comment = payload.applicant_comment
    item.status = "pending"
    item.change_request_reason = None
    item.decision_reason = None
    item.decided_by = None
    item.decided_at = None
    item.revision_count += 1
    item.review_notification_status = "pending"
    item.review_message_id = None
    item.review_notified_at = None
    item.updated_at = datetime.now(UTC)
    session.add(VerificationDecision(request_id=item.id, guild_id=guild_id, action="resubmitted", reason=payload.applicant_comment))
    await session.commit()
    return {"status": "pending", "revision_count": item.revision_count}


@router.get("/discord/guilds/{guild_id}/verification/requests/{request_id}/history")
async def verification_request_history(
    guild_id: int, request_id: uuid.UUID,
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(session, current_user, guild_id)
    rows = (await session.execute(select(VerificationDecision).where(
        VerificationDecision.guild_id == guild_id, VerificationDecision.request_id == request_id
    ).order_by(VerificationDecision.created_at.asc()))).scalars().all()
    return {"items": [{"id": str(x.id), "action": x.action, "reason": x.reason, "actor_user_id": str(x.actor_user_id) if x.actor_user_id else None, "created_at": x.created_at} for x in rows]}


@router.get(
    "/discord/guilds/{guild_id}/verification/export.csv"
)
async def export_verification_csv(
    guild_id: int,
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    query = (
        select(VerificationRequest)
        .where(VerificationRequest.guild_id == guild_id)
        .order_by(VerificationRequest.created_at.desc())
    )

    if status_filter:
        query = query.where(
            VerificationRequest.status == status_filter
        )

    items = list(
        (
            await session.execute(query)
        ).scalars().all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "request_id",
        "discord_user_id",
        "alliance",
        "nickname",
        "requested_nickname",
        "status",
        "retry_count",
        "decision_reason",
        "result_message",
        "created_at",
        "updated_at",
    ])

    for item in items:
        writer.writerow([
            str(item.id),
            item.discord_user_id,
            item.alliance,
            item.nickname,
            item.requested_nickname,
            item.status,
            item.retry_count,
            item.decision_reason or "",
            item.result_message or "",
            item.created_at.isoformat(),
            item.updated_at.isoformat(),
        ])

    content = output.getvalue().encode("utf-8-sig")

    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="verification-{guild_id}.csv"',
        },
    )


@router.post(
    "/discord/guilds/{guild_id}/verification/bulk/cancel"
)
async def bulk_cancel_requests(
    guild_id: int,
    payload: VerificationBulkInput,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.id.in_(payload.request_ids),
            VerificationRequest.status == "pending",
        )
        .values(
            status="cancelled",
            result_message="Cancelled by administrator.",
            processed_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )

    await session.commit()

    return {
        "status": "completed",
        "updated": result.rowcount,
    }


@router.post(
    "/discord/guilds/{guild_id}/verification/bulk/requeue"
)
async def bulk_requeue_requests(
    guild_id: int,
    payload: VerificationBulkInput,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.id.in_(payload.request_ids),
            VerificationRequest.status.in_(
                ["failed", "processing", "approved"]
            ),
        )
        .values(
            status="approved",
            result_message=None,
            last_error=None,
            processed_at=None,
            retry_count=VerificationRequest.retry_count + 1,
            updated_at=datetime.now(UTC),
        )
    )

    await session.commit()

    return {
        "status": "completed",
        "updated": result.rowcount,
    }


@router.post(
    "/discord/guilds/{guild_id}/verification/recover-stale"
)
async def recover_stale_requests(
    guild_id: int,
    payload: VerificationRecoverInput,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    from datetime import timedelta

    await require_guild_management(
        session,
        current_user,
        guild_id,
    )

    threshold = datetime.now(UTC) - timedelta(
        minutes=payload.older_than_minutes
    )

    result = await session.execute(
        update(VerificationRequest)
        .where(
            VerificationRequest.guild_id == guild_id,
            VerificationRequest.status == "processing",
            VerificationRequest.updated_at < threshold,
        )
        .values(
            status="approved",
            last_error="Recovered from stale processing state.",
            retry_count=VerificationRequest.retry_count + 1,
            updated_at=datetime.now(UTC),
        )
    )

    await session.commit()

    return {
        "status": "completed",
        "recovered": result.rowcount,
    }
