"""Target vouchers to a subscription product."""
from alembic import op
import sqlalchemy as sa

revision="0103_voucher_target";down_revision="0102_custom_discord_bot";branch_labels=None;depends_on=None

def upgrade():
    op.add_column("discount_cards",sa.Column("plugin_key",sa.String(length=96),nullable=False,server_default="__paid_modules__"),schema="billing")

def downgrade():
    op.drop_column("discount_cards","plugin_key",schema="billing")
