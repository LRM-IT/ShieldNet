"""Multi-level image verification."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0071_verification_levels"
down_revision = "0070_verification_slash_command"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("levels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("guild_id", sa.BigInteger(), sa.ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("channel_id", sa.BigInteger()), sa.Column("expected_text", sa.String(500), nullable=False, server_default=""),
        sa.Column("role_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("marker", postgresql.JSONB(), nullable=False, server_default='{"x":0,"y":0,"width":1,"height":1}'),
        sa.Column("template_path", sa.String(500)), sa.Column("template_mime", sa.String(100)),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("guild_id", "name", name="uq_verification_level_name"), schema="verification")
    op.create_index("ix_verification_levels_guild_id", "levels", ["guild_id"], schema="verification")
    op.create_table("level_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("level_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("verification.levels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), sa.ForeignKey("discord.guilds.guild_id", ondelete="CASCADE"), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False), sa.Column("discord_message_id", sa.BigInteger(), nullable=False),
        sa.Column("image_url", sa.String(2000), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="processing"),
        sa.Column("matched", sa.Boolean()), sa.Column("detected_text", sa.Text()),
        sa.Column("ai_result", postgresql.JSONB(), nullable=False, server_default="{}"), sa.Column("result_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("completed_at", sa.DateTime(timezone=True)),
        schema="verification")
    op.create_index("ix_verification_level_submissions_level_id", "level_submissions", ["level_id"], schema="verification")
    op.create_index("ix_verification_level_submissions_guild_id", "level_submissions", ["guild_id"], schema="verification")

def downgrade():
    op.drop_table("level_submissions", schema="verification")
    op.drop_table("levels", schema="verification")
