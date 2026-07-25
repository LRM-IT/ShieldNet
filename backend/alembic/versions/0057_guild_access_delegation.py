"""guild access delegation

Revision ID: 0057
Revises: 0056
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "guild_memberships",
        sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="discord",
    )
    op.add_column(
        "guild_memberships",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="discord",
    )
    op.create_index(
        "ix_discord_guild_memberships_expires_at",
        "guild_memberships",
        ["expires_at"],
        schema="discord",
    )


def downgrade():
    op.drop_index("ix_discord_guild_memberships_expires_at", table_name="guild_memberships", schema="discord")
    op.drop_column("guild_memberships", "expires_at", schema="discord")
    op.drop_column("guild_memberships", "permissions", schema="discord")
