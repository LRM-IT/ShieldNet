"""ShieldNet multilingual voting plugin.

Revision ID: 0060_voting_plugin
Revises: 0059_platform_ai_center
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0060_voting_plugin"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voting_polls",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("primary_language", sa.String(length=16), nullable=False, server_default="en"),
        sa.Column("fallback_language", sa.String(length=16), nullable=False, server_default="en"),
        sa.Column("language_selection_mode", sa.String(length=32), nullable=False, server_default="automatic_with_selector"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("selection_mode", sa.String(length=16), nullable=False, server_default="single"),
        sa.Column("anonymous", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_change_vote", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_live_results", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("min_choices", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_choices", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("allowed_role_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["guild_id"], ["discord.guilds.guild_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_voting_polls"),
        schema="discord",
    )
    op.create_index("ix_voting_polls_guild_id", "voting_polls", ["guild_id"], schema="discord")
    op.create_index("ix_voting_polls_status", "voting_polls", ["status"], schema="discord")

    op.create_table(
        "voting_poll_translations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("poll_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language_code", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("completion_message", sa.Text(), nullable=True),
        sa.Column("translation_source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("ai_provider", sa.String(length=64), nullable=True),
        sa.Column("ai_model", sa.String(length=128), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("translated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["poll_id"], ["discord.voting_polls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_voting_poll_translations"),
        sa.UniqueConstraint("poll_id", "language_code", name="uq_voting_poll_language"),
        schema="discord",
    )
    op.create_index("ix_voting_poll_translations_poll_id", "voting_poll_translations", ["poll_id"], schema="discord")

    op.create_table(
        "voting_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("poll_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("emoji", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["poll_id"], ["discord.voting_polls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_voting_options"),
        sa.UniqueConstraint("poll_id", "position", name="uq_voting_option_position"),
        schema="discord",
    )
    op.create_index("ix_voting_options_poll_id", "voting_options", ["poll_id"], schema="discord")

    op.create_table(
        "voting_option_translations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("option_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language_code", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["option_id"], ["discord.voting_options.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_voting_option_translations"),
        sa.UniqueConstraint("option_id", "language_code", name="uq_voting_option_language"),
        schema="discord",
    )
    op.create_index("ix_voting_option_translations_option_id", "voting_option_translations", ["option_id"], schema="discord")

    op.create_table(
        "voting_votes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("poll_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("option_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("language_code", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["poll_id"], ["discord.voting_polls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["option_id"], ["discord.voting_options.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_voting_votes"),
        sa.UniqueConstraint("poll_id", "discord_user_id", "option_id", name="uq_voting_user_option"),
        schema="discord",
    )
    op.create_index("ix_voting_votes_poll_id", "voting_votes", ["poll_id"], schema="discord")
    op.create_index("ix_voting_votes_option_id", "voting_votes", ["option_id"], schema="discord")
    op.create_index("ix_voting_votes_discord_user_id", "voting_votes", ["discord_user_id"], schema="discord")

    op.create_table(
        "voting_publication_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("poll_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["poll_id"], ["discord.voting_polls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_voting_publication_jobs"),
        schema="discord",
    )
    op.create_index("ix_voting_publication_jobs_poll_id", "voting_publication_jobs", ["poll_id"], schema="discord")
    op.create_index("ix_voting_publication_jobs_status", "voting_publication_jobs", ["status"], schema="discord")

    # Runtime user can use created objects, but cannot alter the schema.
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'shieldnet_backend') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON
          discord.voting_polls,
          discord.voting_poll_translations,
          discord.voting_options,
          discord.voting_option_translations,
          discord.voting_votes,
          discord.voting_publication_jobs
        TO shieldnet_backend;

        GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA discord
        TO shieldnet_backend;
      END IF;
    END
    $$;
    """)


def downgrade() -> None:
    op.drop_index("ix_voting_publication_jobs_status", table_name="voting_publication_jobs", schema="discord")
    op.drop_index("ix_voting_publication_jobs_poll_id", table_name="voting_publication_jobs", schema="discord")
    op.drop_table("voting_publication_jobs", schema="discord")

    op.drop_index("ix_voting_votes_discord_user_id", table_name="voting_votes", schema="discord")
    op.drop_index("ix_voting_votes_option_id", table_name="voting_votes", schema="discord")
    op.drop_index("ix_voting_votes_poll_id", table_name="voting_votes", schema="discord")
    op.drop_table("voting_votes", schema="discord")

    op.drop_index("ix_voting_option_translations_option_id", table_name="voting_option_translations", schema="discord")
    op.drop_table("voting_option_translations", schema="discord")

    op.drop_index("ix_voting_options_poll_id", table_name="voting_options", schema="discord")
    op.drop_table("voting_options", schema="discord")

    op.drop_index("ix_voting_poll_translations_poll_id", table_name="voting_poll_translations", schema="discord")
    op.drop_table("voting_poll_translations", schema="discord")

    op.drop_index("ix_voting_polls_status", table_name="voting_polls", schema="discord")
    op.drop_index("ix_voting_polls_guild_id", table_name="voting_polls", schema="discord")
    op.drop_table("voting_polls", schema="discord")
