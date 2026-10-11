"""Multilingual idea surveys and private responses."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
revision = "0109_idea_collection"
down_revision = "0108_translation_traffic"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("idea_surveys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("guild_id", sa.BigInteger(), sa.ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration", JSONB(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("message_id", sa.BigInteger()),
        sa.Column("job_status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("claim_id", UUID(as_uuid=True)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="discord")
    op.create_index("ix_discord_idea_surveys_guild_id", "idea_surveys", ["guild_id"], schema="discord")
    op.create_table("idea_responses",
        sa.Column("survey_id", UUID(as_uuid=True), sa.ForeignKey("discord.idea_surveys.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="discord")


def downgrade():
    op.drop_table("idea_responses", schema="discord")
    op.drop_table("idea_surveys", schema="discord")
