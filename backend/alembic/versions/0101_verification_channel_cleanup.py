"""Add verification channel cleanup interval.

Revision ID: 0101_verification_cleanup
Revises: 0100_subscription_day_vouchers
"""
from alembic import op
import sqlalchemy as sa

revision = "0101_verification_cleanup"
down_revision = "0100_subscription_day_vouchers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("channel_cleanup_minutes", sa.Integer(), nullable=False, server_default="0"),
        schema="verification",
    )


def downgrade() -> None:
    op.drop_column("settings", "channel_cleanup_minutes", schema="verification")
