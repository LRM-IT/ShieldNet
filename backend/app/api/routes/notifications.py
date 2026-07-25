from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db_session
from app.models.core import GlobalRole, User
from app.models.notifications import PlatformNotification
from app.core.events import Event, event_bus
from app.services.audit_service import AuditService
from app.services.global_access import GlobalAccessService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/platform/notifications", tags=["Platform Notifications"])


def _require(user: User) -> None:
    GlobalAccessService.require_any(user, (GlobalRole.SUPERADMIN, GlobalRole.ADMIN))


def _serialize(item: PlatformNotification) -> dict:
    return {
        "id": str(item.id),
        "guild_id": str(item.guild_id) if item.guild_id is not None else None,
        "severity": item.severity,
        "category": item.category,
        "source": item.source,
        "title": item.title,
        "message": item.message,
        "status": item.status,
        "metadata": item.metadata_json,
        "first_seen_at": item.first_seen_at.isoformat(),
        "last_seen_at": item.last_seen_at.isoformat(),
        "acknowledged_at": item.acknowledged_at.isoformat() if item.acknowledged_at else None,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
    }


@router.get("")
async def list_notifications(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require(current_user)
    filters = []
    if status:
        filters.append(PlatformNotification.status == status)
    if severity:
        filters.append(PlatformNotification.severity == severity)
    total = int((await session.execute(select(func.count(PlatformNotification.id)).where(*filters))).scalar_one())
    items = list((await session.scalars(
        select(PlatformNotification)
        .where(*filters)
        .order_by(PlatformNotification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).all())
    return {"items": [_serialize(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.get("/summary")
async def notification_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require(current_user)
    return await NotificationService(session).summary()


@router.post("/evaluate")
async def evaluate_notifications(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require(current_user)
    result = await NotificationService(session).evaluate()
    await AuditService(session).record(
        event_type="platform.notifications.evaluate",
        actor_user_id=current_user.id,
        target_type="notification-center",
        result="completed",
        message="Platform alert rules evaluated.",
        payload=result,
    )
    await session.commit()
    await event_bus.publish(Event(
        name="notification.summary.updated",
        payload=result,
        actor_id=current_user.discord_user_id,
        source="notification-center",
    ))
    return result


async def _change_status(notification_id: UUID, status: str, current_user: User, session: AsyncSession) -> dict:
    item = await session.get(PlatformNotification, notification_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    now = datetime.now(UTC)
    item.status = status
    if status == "acknowledged":
        item.acknowledged_by = current_user.id
        item.acknowledged_at = now
    elif status == "resolved":
        item.resolved_by = current_user.id
        item.resolved_at = now
    await AuditService(session).record(
        event_type=f"platform.notification.{status}",
        guild_id=item.guild_id,
        actor_user_id=current_user.id,
        target_type="notification",
        target_id=str(item.id),
        result=status,
        message=f"Notification marked as {status}.",
    )
    await session.commit()
    await session.refresh(item)
    serialized = _serialize(item)
    await event_bus.publish(Event(
        name="notification.status.changed",
        payload=serialized,
        guild_id=item.guild_id,
        actor_id=current_user.discord_user_id,
        source="notification-center",
    ))
    return serialized


@router.post("/{notification_id}/acknowledge")
async def acknowledge_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require(current_user)
    return await _change_status(notification_id, "acknowledged", current_user, session)


@router.post("/{notification_id}/resolve")
async def resolve_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require(current_user)
    return await _change_status(notification_id, "resolved", current_user, session)
