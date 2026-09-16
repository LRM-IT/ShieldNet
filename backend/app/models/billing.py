import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class BillingPluginPlan(Base, TimestampMixin):
    __tablename__ = "plugin_plans"
    __table_args__ = (UniqueConstraint("plugin_key", name="uq_billing_plugin_plan_key"), {"schema": "billing"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_key: Mapped[str] = mapped_column(String(96), nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="UAH", server_default="UAH")
    monthly_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quarterly_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    yearly_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))


class BillingSubscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("guild_id", "plugin_key", name="uq_billing_subscription_guild_plugin"), {"schema": "billing"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"), nullable=False)
    plugin_key: Mapped[str] = mapped_column(String(96), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", server_default="active")
    billing_period: Mapped[str] = mapped_column(String(16), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(24))
    external_order_id: Mapped[str | None] = mapped_column(String(160))
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="SET NULL"))


class BillingPayment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("order_reference", name="uq_billing_payment_order_reference"), {"schema": "billing"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"), nullable=False)
    plugin_key: Mapped[str] = mapped_column(String(96), nullable=False)
    billing_period: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", server_default="created")
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    provider_payment_id: Mapped[str | None] = mapped_column(String(160))
    checkout_url: Mapped[str | None] = mapped_column(Text)
    raw_status: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    base_amount_uah: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    quote_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingWallet(Base, TimestampMixin):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("discord_user_id", "currency", name="uq_billing_wallet_owner_currency"), {"schema": "billing"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="UAH", server_default="UAH")


class BillingWalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = ({"schema": "billing"},)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("billing.wallets.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("billing.payments.id", ondelete="SET NULL"))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BillingExchangeRate(Base, TimestampMixin):
    __tablename__ = "exchange_rates"
    __table_args__ = (UniqueConstraint("currency", name="uq_billing_exchange_rate_currency"), {"schema": "billing"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    uah_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="NBU", server_default="NBU")
