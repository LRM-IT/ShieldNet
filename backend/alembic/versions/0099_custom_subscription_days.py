"""Store the purchased duration for custom server subscriptions."""

from alembic import op
import sqlalchemy as sa


revision = "0099_custom_subscription_days"
down_revision = "0098_disable_subscription_auto_renew"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payments", sa.Column("access_days", sa.Integer(), nullable=True), schema="billing")


def downgrade():
    op.drop_column("payments", "access_days", schema="billing")
