"""Allow vouchers to grant server subscription days directly."""

from alembic import op
import sqlalchemy as sa


revision = "0100_subscription_day_vouchers"
down_revision = "0099_custom_subscription_days"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("discount_cards", sa.Column("access_days", sa.Integer(), nullable=True), schema="billing")


def downgrade():
    op.drop_column("discount_cards", "access_days", schema="billing")
