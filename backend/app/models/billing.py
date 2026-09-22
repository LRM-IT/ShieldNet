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
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    monthly_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quarterly_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    yearly_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quarterly_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    yearly_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")


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
    owner_discord_id: Mapped[int | None] = mapped_column(BigInteger)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    expiry_notice_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    expiry_notice_days: Mapped[int] = mapped_column(nullable=False, default=3, server_default="3")
    expiry_notice_discord_dm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    expiry_notice_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    expiry_notice_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiry_notice_for_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiry_dm_notice_for_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expiry_email_notice_for_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingPayment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("order_reference", name="uq_billing_payment_order_reference"), {"schema": "billing"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"))
    plugin_key: Mapped[str | None] = mapped_column(String(96))
    billing_period: Mapped[str | None] = mapped_column(String(16))
    access_days: Mapped[int | None] = mapped_column()
    purpose: Mapped[str] = mapped_column(String(24), nullable=False, default="subscription", server_default="subscription")
    owner_discord_id: Mapped[int | None] = mapped_column(BigInteger)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", server_default="created")
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    provider_payment_id: Mapped[str | None] = mapped_column(String(160))
    checkout_url: Mapped[str | None] = mapped_column(Text)
    raw_status: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    base_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quote_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    original_amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    discount_code: Mapped[str | None] = mapped_column(String(64))


class BillingWallet(Base, TimestampMixin):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("discord_user_id", "currency", name="uq_billing_wallet_owner_currency"), {"schema": "billing"})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    discord_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default="USD")
    low_balance_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    low_balance_threshold: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    low_balance_discord_dm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    low_balance_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    low_balance_notice_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    low_balance_dm_notice_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    low_balance_email_notice_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class BillingDiscountCard(Base, TimestampMixin):
    __tablename__ = "discount_cards"
    __table_args__ = (UniqueConstraint("code", name="uq_billing_discount_card_code"), {"schema": "billing"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_redemptions: Mapped[int | None] = mapped_column()
    redemptions: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")

class BillingDiscountRedemption(Base):
    __tablename__ = "discount_redemptions"
    __table_args__ = (UniqueConstraint("card_id", "redeemed_by_user_id", name="uq_billing_voucher_redemption_user"), {"schema": "billing"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    card_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("billing.discount_cards.id", ondelete="CASCADE"), nullable=False)
    guild_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("discord.guilds.guild_id", ondelete="SET NULL"))
    redeemed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.users.id", ondelete="SET NULL"))
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

class BillingTenureDiscount(Base, TimestampMixin):
    __tablename__ = "tenure_discounts"
    __table_args__ = (UniqueConstraint("minimum_months", name="uq_billing_tenure_discount_months"), {"schema": "billing"})
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    minimum_months: Mapped[int] = mapped_column(nullable=False)
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
