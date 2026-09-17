"""Add wallet notification channels.

Revision ID: 0086_wallet_notification_channels
Revises: 0085_user_regional_preferences
"""
from alembic import op
import sqlalchemy as sa

revision = "0086_wallet_notification_channels"
down_revision = "0085_user_regional_preferences"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("wallets", sa.Column("low_balance_discord_dm", sa.Boolean(), nullable=False, server_default=sa.text("true")), schema="billing")
    op.add_column("wallets", sa.Column("low_balance_email", sa.Boolean(), nullable=False, server_default=sa.text("false")), schema="billing")

def downgrade():
    op.drop_column("wallets", "low_balance_email", schema="billing")
    op.drop_column("wallets", "low_balance_discord_dm", schema="billing")
