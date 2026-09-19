from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.core import User
from app.models.support import SupportTicket, SupportTicketMessage

router = APIRouter(prefix="/support/tickets", tags=["Support tickets"])

class TicketCreate(BaseModel):
    topic: str = Field(pattern=r"^(bug|suggestion)$")
    subject: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=3, max_length=10000)

class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)

class TicketUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(open|in_progress|resolved|closed)$")
    priority: str | None = Field(default=None, pattern=r"^(low|normal|high|urgent)$")

def ticket_dict(ticket: SupportTicket, author: User | None = None):
    return {"id": ticket.id, "topic": ticket.topic, "subject": ticket.subject, "status": ticket.status,
            "priority": ticket.priority, "author_user_id": ticket.author_user_id,
            "author_name": (author.display_name or author.login) if author else None,
            "author_email": author.email if author else None, "created_at": ticket.created_at,
            "updated_at": ticket.updated_at, "closed_at": ticket.closed_at}

async def accessible_ticket(session: AsyncSession, ticket_id: UUID, user: User, staff: bool = False):
    ticket = await session.get(SupportTicket, ticket_id)
    if not ticket or (not staff and ticket.author_user_id != user.id):
        raise HTTPException(404, "Ticket not found")
    return ticket

@router.post("")
async def create_ticket(payload: TicketCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    ticket = SupportTicket(id=uuid4(), author_user_id=user.id, topic=payload.topic, subject=payload.subject.strip())
    session.add(ticket); await session.flush()
    session.add(SupportTicketMessage(id=uuid4(), ticket_id=ticket.id, author_user_id=user.id, body=payload.body.strip(), is_staff=False))
    await session.commit(); await session.refresh(ticket)
    return ticket_dict(ticket, user)

@router.get("")
async def my_tickets(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    rows = list((await session.execute(select(SupportTicket).where(SupportTicket.author_user_id == user.id).order_by(SupportTicket.updated_at.desc()))).scalars())
    return [ticket_dict(row, user) for row in rows]

@router.get("/{ticket_id:uuid}")
async def get_ticket(ticket_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user)
    messages = list((await session.execute(select(SupportTicketMessage, User).join(User, User.id == SupportTicketMessage.author_user_id).where(SupportTicketMessage.ticket_id == ticket.id).order_by(SupportTicketMessage.created_at))).all())
    return {**ticket_dict(ticket, user), "messages": [{"id": m.id, "body": m.body, "is_staff": m.is_staff, "author_name": a.display_name or a.login, "created_at": m.created_at} for m,a in messages]}

@router.post("/{ticket_id:uuid}/messages")
async def reply(ticket_id: UUID, payload: MessageCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user)
    if ticket.status == "closed": raise HTTPException(409, "Ticket is closed")
    session.add(SupportTicketMessage(id=uuid4(), ticket_id=ticket.id, author_user_id=user.id, body=payload.body.strip(), is_staff=False))
    ticket.updated_at = datetime.now(timezone.utc); await session.commit(); return {"sent": True}

@router.get("/platform/all")
async def all_tickets(status: str | None = Query(None), _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    query = select(SupportTicket, User).join(User, User.id == SupportTicket.author_user_id)
    if status: query = query.where(SupportTicket.status == status)
    rows = (await session.execute(query.order_by(SupportTicket.updated_at.desc()))).all()
    return [ticket_dict(t, u) for t,u in rows]

@router.get("/platform/{ticket_id}")
async def staff_ticket(ticket_id: UUID, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user, True); author = await session.get(User, ticket.author_user_id)
    messages = list((await session.execute(select(SupportTicketMessage, User).join(User, User.id == SupportTicketMessage.author_user_id).where(SupportTicketMessage.ticket_id == ticket.id).order_by(SupportTicketMessage.created_at))).all())
    return {**ticket_dict(ticket, author), "messages": [{"id": m.id, "body": m.body, "is_staff": m.is_staff, "author_name": a.display_name or a.login, "created_at": m.created_at} for m,a in messages]}

@router.post("/platform/{ticket_id}/messages")
async def staff_reply(ticket_id: UUID, payload: MessageCreate, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user, True)
    session.add(SupportTicketMessage(id=uuid4(), ticket_id=ticket.id, author_user_id=user.id, body=payload.body.strip(), is_staff=True))
    if ticket.status == "open": ticket.status = "in_progress"
    ticket.updated_at = datetime.now(timezone.utc); await session.commit(); return {"sent": True}

@router.patch("/platform/{ticket_id}")
async def update_ticket(ticket_id: UUID, payload: TicketUpdate, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user, True)
    if payload.status is not None:
        ticket.status = payload.status; ticket.closed_at = datetime.now(timezone.utc) if payload.status == "closed" else None
    if payload.priority is not None: ticket.priority = payload.priority
    await session.commit(); return ticket_dict(ticket)
