from datetime import datetime, timezone
from uuid import UUID, uuid4
from pathlib import Path
from io import BytesIO
from PIL import Image

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.platform_access import require_superadmin
from app.db.session import get_db_session
from app.models.core import User
from app.models.support import SupportTicket, SupportTicketMessage, SupportTicketAttachment
from app.services.global_access import GlobalAccessService

router = APIRouter(prefix="/support/tickets", tags=["Support tickets"])
ATTACHMENT_ROOT = Path("/var/lib/shieldnet/media-assets/support-tickets")
ALLOWED_IMAGES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024

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

async def message_dicts(session: AsyncSession, ticket_id: UUID):
    rows = list((await session.execute(select(SupportTicketMessage, User).join(User, User.id == SupportTicketMessage.author_user_id).where(SupportTicketMessage.ticket_id == ticket_id).order_by(SupportTicketMessage.created_at))).all())
    ids = [m.id for m,_ in rows]
    attachments = list((await session.execute(select(SupportTicketAttachment).where(SupportTicketAttachment.message_id.in_(ids)))).scalars()) if ids else []
    grouped = {}
    for item in attachments: grouped.setdefault(item.message_id, []).append({"id": item.id, "file_name": item.file_name, "mime_type": item.mime_type, "file_size": item.file_size})
    return [{"id": m.id, "body": m.body, "is_staff": m.is_staff, "author_name": a.display_name or a.login, "created_at": m.created_at, "attachments": grouped.get(m.id, [])} for m,a in rows]

@router.post("")
async def create_ticket(payload: TicketCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    ticket = SupportTicket(id=uuid4(), author_user_id=user.id, topic=payload.topic, subject=payload.subject.strip())
    session.add(ticket); await session.flush()
    message = SupportTicketMessage(id=uuid4(), ticket_id=ticket.id, author_user_id=user.id, body=payload.body.strip(), is_staff=False); session.add(message)
    await session.commit(); await session.refresh(ticket)
    return {**ticket_dict(ticket, user), "message_id": message.id}

@router.get("")
async def my_tickets(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    rows = list((await session.execute(select(SupportTicket).where(SupportTicket.author_user_id == user.id).order_by(SupportTicket.updated_at.desc()))).scalars())
    return [ticket_dict(row, user) for row in rows]

@router.get("/{ticket_id:uuid}")
async def get_ticket(ticket_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user)
    return {**ticket_dict(ticket, user), "messages": await message_dicts(session, ticket.id)}

@router.post("/{ticket_id:uuid}/messages")
async def reply(ticket_id: UUID, payload: MessageCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user)
    if ticket.status == "closed": raise HTTPException(409, "Ticket is closed")
    message = SupportTicketMessage(id=uuid4(), ticket_id=ticket.id, author_user_id=user.id, body=payload.body.strip(), is_staff=False); session.add(message)
    ticket.updated_at = datetime.now(timezone.utc); await session.commit(); return {"sent": True, "message_id": message.id}

@router.get("/platform/all")
async def all_tickets(status: str | None = Query(None), _: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    query = select(SupportTicket, User).join(User, User.id == SupportTicket.author_user_id)
    if status: query = query.where(SupportTicket.status == status)
    rows = (await session.execute(query.order_by(SupportTicket.updated_at.desc()))).all()
    return [ticket_dict(t, u) for t,u in rows]

@router.get("/platform/{ticket_id}")
async def staff_ticket(ticket_id: UUID, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user, True); author = await session.get(User, ticket.author_user_id)
    return {**ticket_dict(ticket, author), "messages": await message_dicts(session, ticket.id)}

@router.post("/platform/{ticket_id}/messages")
async def staff_reply(ticket_id: UUID, payload: MessageCreate, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user, True)
    message = SupportTicketMessage(id=uuid4(), ticket_id=ticket.id, author_user_id=user.id, body=payload.body.strip(), is_staff=True); session.add(message)
    if ticket.status == "open": ticket.status = "in_progress"
    ticket.updated_at = datetime.now(timezone.utc); await session.commit(); return {"sent": True, "message_id": message.id}

@router.post("/{ticket_id:uuid}/messages/{message_id:uuid}/attachments")
async def upload_attachments(ticket_id: UUID, message_id: UUID, files: list[UploadFile] = File(...), user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user, GlobalAccessService.is_superadmin(user))
    message = await session.get(SupportTicketMessage, message_id)
    if not message or message.ticket_id != ticket.id or message.author_user_id != user.id: raise HTTPException(404, "Message not found")
    if len(files) > 5: raise HTTPException(422, "Maximum 5 images per message")
    saved=[]
    for upload in files:
        if upload.content_type not in ALLOWED_IMAGES: raise HTTPException(422, "Only PNG, JPEG, WebP and GIF images are allowed")
        content=await upload.read(MAX_IMAGE_SIZE + 1)
        if len(content)>MAX_IMAGE_SIZE: raise HTTPException(413, "Image exceeds 10 MB")
        try:
            with Image.open(BytesIO(content)) as image: image.verify()
        except Exception as exc: raise HTTPException(422,"Invalid image file") from exc
        suffix={"image/png":".png","image/jpeg":".jpg","image/webp":".webp","image/gif":".gif"}[upload.content_type]
        attachment_id=uuid4(); folder=ATTACHMENT_ROOT/str(ticket.id); folder.mkdir(parents=True,exist_ok=True); path=folder/f"{attachment_id}{suffix}"; path.write_bytes(content)
        row=SupportTicketAttachment(id=attachment_id,message_id=message.id,file_name=(upload.filename or "image")[:255],file_path=str(path),mime_type=upload.content_type,file_size=len(content));session.add(row);saved.append(row)
    await session.commit();return [{"id":x.id,"file_name":x.file_name,"mime_type":x.mime_type,"file_size":x.file_size} for x in saved]

@router.get("/{ticket_id:uuid}/attachments/{attachment_id:uuid}")
async def attachment_file(ticket_id: UUID, attachment_id: UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    ticket=await accessible_ticket(session,ticket_id,user,GlobalAccessService.is_superadmin(user)); row=await session.get(SupportTicketAttachment,attachment_id)
    message=await session.get(SupportTicketMessage,row.message_id) if row else None
    if not row or not message or message.ticket_id!=ticket.id: raise HTTPException(404,"Attachment not found")
    path=Path(row.file_path)
    if not path.is_file(): raise HTTPException(404,"Attachment file not found")
    return Response(content=path.read_bytes(),media_type=row.mime_type)

@router.patch("/platform/{ticket_id}")
async def update_ticket(ticket_id: UUID, payload: TicketUpdate, user: User = Depends(require_superadmin), session: AsyncSession = Depends(get_db_session)):
    ticket = await accessible_ticket(session, ticket_id, user, True)
    if payload.status is not None:
        ticket.status = payload.status; ticket.closed_at = datetime.now(timezone.utc) if payload.status == "closed" else None
    if payload.priority is not None: ticket.priority = payload.priority
    await session.commit(); return ticket_dict(ticket)
