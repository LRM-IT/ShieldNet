"""Record subscription day transfers between owned servers."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0104_subscription_transfers"
down_revision = "0103_voucher_target"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subscription_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_guild_id", sa.BigInteger(), sa.ForeignKey("discord.guilds.guild_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("target_guild_id", sa.BigInteger(), sa.ForeignKey("discord.guilds.guild_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plugin_key", sa.String(length=96), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("source_expires_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_expires_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_expires_before", sa.DateTime(timezone=True), nullable=True),
        sa.Column("target_expires_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="billing",
    )
    op.create_index("ix_billing_subscription_transfers_user", "subscription_transfers", ["requested_by_user_id", "created_at"], schema="billing")


def downgrade():
    op.drop_index("ix_billing_subscription_transfers_user", table_name="subscription_transfers", schema="billing")
    op.drop_table("subscription_transfers", schema="billing")
