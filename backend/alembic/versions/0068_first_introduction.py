"""First introduction plugin profiles.

Revision ID: 0068_first_introduction
Revises: 0067_voting_template
"""
from alembic import op
import sqlalchemy as sa

revision = "0068_first_introduction"
down_revision = "0067_voting_template"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "first_introduction_profiles",
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("language_code", sa.String(16), nullable=False),
        sa.Column("server_number", sa.String(32), nullable=False),
        sa.Column("alliance", sa.String(32), nullable=False),
        sa.Column("nickname", sa.String(64), nullable=False),
        sa.Column("applied_nickname", sa.String(32), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["guild_id"], ["discord.guilds.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("guild_id", "discord_user_id"),
        schema="discord",
    )


def downgrade():
    op.drop_table("first_introduction_profiles", schema="discord")
