import enum, uuid
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin

class GuildStatus(str, enum.Enum):
    ACTIVE='active'; INACTIVE='inactive'; BLOCKED='blocked'; LEFT='left'; NEED_SETUP='need_setup'
class BotStatus(str, enum.Enum):
    ONLINE='online'; OFFLINE='offline'; REMOVED='removed'; ERROR='error'
class MembershipRole(str, enum.Enum):
    ADMIN='admin'; MODERATOR='moderator'
class MembershipStatus(str, enum.Enum):
    ACTIVE='active'; PENDING='pending'; REVOKED='revoked'

class Guild(Base, TimestampMixin):
    __tablename__='guilds'; __table_args__=(Index('ix_discord_guilds_owner','owner_discord_id'),{'schema':'discord'})
    guild_id: Mapped[int]=mapped_column(BigInteger,primary_key=True)
    name: Mapped[str]=mapped_column(String(255),nullable=False)
    icon_url: Mapped[str|None]=mapped_column(Text)
    owner_discord_id: Mapped[int]=mapped_column(BigInteger,nullable=False)
    member_count: Mapped[int]=mapped_column(Integer,nullable=False,default=0,server_default='0')
    preferred_language: Mapped[str]=mapped_column(String(16),nullable=False,default='uk',server_default='uk')
    status: Mapped[GuildStatus]=mapped_column(Enum(GuildStatus,name='guild_status',schema='discord',values_callable=lambda c:[i.value for i in c]),nullable=False,server_default='need_setup')
    bot_status: Mapped[BotStatus]=mapped_column(Enum(BotStatus,name='bot_status',schema='discord',values_callable=lambda c:[i.value for i in c]),nullable=False,server_default='online')
    joined_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,server_default=func.now())
    left_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class GuildMembership(Base, TimestampMixin):
    __tablename__='guild_memberships'
    __table_args__=(UniqueConstraint('guild_id','discord_user_id',name='uq_discord_guild_membership_user'),Index('ix_discord_memberships_user_id','user_id'),{'schema':'discord'})
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    guild_id: Mapped[int]=mapped_column(BigInteger,ForeignKey('discord.guilds.guild_id',ondelete='CASCADE'),nullable=False)
    user_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('core.users.id',ondelete='SET NULL'))
    discord_user_id: Mapped[int]=mapped_column(BigInteger,nullable=False)
    role: Mapped[MembershipRole]=mapped_column(Enum(MembershipRole,name='membership_role',schema='discord',values_callable=lambda c:[i.value for i in c]),nullable=False)
    status: Mapped[MembershipStatus]=mapped_column(Enum(MembershipStatus,name='membership_status',schema='discord',values_callable=lambda c:[i.value for i in c]),nullable=False,server_default='pending')
    created_by: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('core.users.id',ondelete='SET NULL'))
    permissions: Mapped[dict]=mapped_column(JSONB,nullable=False,default=dict,server_default='{}')
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
