"""Track billing reminder delivery separately per channel."""
from alembic import op
import sqlalchemy as sa

revision="0095_billing_delivery_channels";down_revision="0094_billing_reminders";branch_labels=None;depends_on=None

def upgrade():
    op.add_column("wallets",sa.Column("low_balance_dm_notice_sent_at",sa.DateTime(timezone=True)),schema="billing")
    op.add_column("wallets",sa.Column("low_balance_email_notice_sent_at",sa.DateTime(timezone=True)),schema="billing")
    op.add_column("subscriptions",sa.Column("expiry_dm_notice_for_expires_at",sa.DateTime(timezone=True)),schema="billing")
    op.add_column("subscriptions",sa.Column("expiry_email_notice_for_expires_at",sa.DateTime(timezone=True)),schema="billing")

def downgrade():
    op.drop_column("subscriptions","expiry_email_notice_for_expires_at",schema="billing");op.drop_column("subscriptions","expiry_dm_notice_for_expires_at",schema="billing")
    op.drop_column("wallets","low_balance_email_notice_sent_at",schema="billing");op.drop_column("wallets","low_balance_dm_notice_sent_at",schema="billing")
