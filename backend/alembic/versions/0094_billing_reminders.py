"""Add delivery state and server subscription reminders."""
from alembic import op
import sqlalchemy as sa

revision = "0094_billing_reminders"
down_revision = "0093_support_attachments"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("wallets", sa.Column("low_balance_notice_sent_at", sa.DateTime(timezone=True)), schema="billing")
    op.add_column("subscriptions", sa.Column("expiry_notice_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")), schema="billing")
    op.add_column("subscriptions", sa.Column("expiry_notice_days", sa.Integer(), nullable=False, server_default="3"), schema="billing")
    op.add_column("subscriptions", sa.Column("expiry_notice_discord_dm", sa.Boolean(), nullable=False, server_default=sa.text("true")), schema="billing")
    op.add_column("subscriptions", sa.Column("expiry_notice_email", sa.Boolean(), nullable=False, server_default=sa.text("false")), schema="billing")
    op.add_column("subscriptions", sa.Column("expiry_notice_sent_at", sa.DateTime(timezone=True)), schema="billing")
    op.add_column("subscriptions", sa.Column("expiry_notice_for_expires_at", sa.DateTime(timezone=True)), schema="billing")

def downgrade():
    for column in ("expiry_notice_for_expires_at","expiry_notice_sent_at","expiry_notice_email","expiry_notice_discord_dm","expiry_notice_days","expiry_notice_enabled"):
        op.drop_column("subscriptions", column, schema="billing")
    op.drop_column("wallets", "low_balance_notice_sent_at", schema="billing")
