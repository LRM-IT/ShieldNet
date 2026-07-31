from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.core import Base

class UserLanguage(Base):
    __tablename__ = "user_languages"
    __table_args__ = (UniqueConstraint("user_id","language_code",name="uq_platform_user_languages_user_code"),{"schema":"platform"})
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True),ForeignKey("core.users.id",ondelete="CASCADE"),nullable=False,index=True)
    language_code: Mapped[str] = mapped_column(String(16),ForeignKey("platform.global_languages.code",ondelete="CASCADE"),nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean,nullable=False,default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)
    sort_order: Mapped[int] = mapped_column(Integer,nullable=False,default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now(),onupdate=func.now())
