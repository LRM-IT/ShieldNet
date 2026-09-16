"""Billing plans, subscriptions and verified payments.

Revision ID: 0073_billing_core
Revises: 0072_verification_level_criteria
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0073_billing_core"
down_revision = "0072_verification_level_criteria"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS billing")
    op.create_table("plugin_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plugin_key", sa.String(96), nullable=False),
        sa.Column("is_free", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("currency", sa.String(3), nullable=False, server_default="UAH"),
        sa.Column("monthly_price", sa.Numeric(12,2)), sa.Column("quarterly_price", sa.Numeric(12,2)), sa.Column("yearly_price", sa.Numeric(12,2)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("plugin_key", name="uq_billing_plugin_plan_key"), schema="billing")
    op.create_table("subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("plugin_key", sa.String(96), nullable=False), sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("billing_period", sa.String(16), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("provider", sa.String(24)), sa.Column("external_order_id", sa.String(160)),
        sa.Column("granted_by_user_id", postgresql.UUID(as_uuid=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["guild_id"],["discord.guilds.guild_id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_user_id"],["core.users.id"],ondelete="SET NULL"),
        sa.UniqueConstraint("guild_id","plugin_key",name="uq_billing_subscription_guild_plugin"), schema="billing")
    op.create_table("payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("order_reference", sa.String(160), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False), sa.Column("plugin_key", sa.String(96), nullable=False), sa.Column("billing_period", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(24), nullable=False), sa.Column("amount", sa.Numeric(12,2), nullable=False), sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"), sa.Column("signature_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("provider_payment_id", sa.String(160)), sa.Column("checkout_url", sa.Text()), sa.Column("raw_status", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("paid_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["guild_id"],["discord.guilds.guild_id"],ondelete="CASCADE"),
        sa.UniqueConstraint("order_reference",name="uq_billing_payment_order_reference"), schema="billing")
    free = ["welcome","audit_security","backup_restore","guild-dm-broadcast","antiflood","ai_automod"]
    for key in free:
        op.execute(sa.text("INSERT INTO billing.plugin_plans(id,plugin_key,is_free,enabled) VALUES(gen_random_uuid(),:key,true,true) ON CONFLICT(plugin_key) DO NOTHING").bindparams(key=key))

def downgrade():
    op.drop_table("payments", schema="billing")
    op.drop_table("subscriptions", schema="billing")
    op.drop_table("plugin_plans", schema="billing")
    op.execute("DROP SCHEMA IF EXISTS billing")

