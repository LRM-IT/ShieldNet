"""Persist user regional preferences.

Revision ID: 0085_user_regional_preferences
Revises: 0084_activation_period_discounts
"""
from alembic import op
import sqlalchemy as sa

revision="0085_user_regional_preferences"
down_revision="0084_activation_period_discounts"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("users",sa.Column("preferred_locale",sa.String(8)),schema="core")
    op.add_column("users",sa.Column("preferred_timezone",sa.String(64)),schema="core")
    op.add_column("users",sa.Column("display_currency",sa.String(3)),schema="core")
    op.add_column("users",sa.Column("use_discord_locale",sa.Boolean(),nullable=False,server_default=sa.text("false")),schema="core")

def downgrade():
    op.drop_column("users","use_discord_locale",schema="core")
    op.drop_column("users","display_currency",schema="core")
    op.drop_column("users","preferred_timezone",schema="core")
    op.drop_column("users","preferred_locale",schema="core")
