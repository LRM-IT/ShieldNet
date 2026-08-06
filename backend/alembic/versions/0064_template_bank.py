"""Platform Template Bank.

Revision ID: 0064_template_bank
Revises: 0063_voting_results
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0064_template_bank"
down_revision = "0063_voting_results"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS media")
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("default_qr_url", sa.String(1000), nullable=False, server_default="https://discord.lrm-it.com"),
        sa.Column("default_qr_caption", sa.String(255), nullable=False, server_default="Visit our website"),
        sa.Column("allow_guild_qr_override", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="media",
    )
    op.execute("""
      INSERT INTO media.settings(id,default_qr_url,default_qr_caption,allow_guild_qr_override)
      VALUES(1,'https://discord.lrm-it.com','Visit our website',false)
      ON CONFLICT(id) DO NOTHING
    """)
    op.create_table(
        "templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("subcategory", sa.String(80)),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("canvas_width", sa.Integer(), nullable=False),
        sa.Column("canvas_height", sa.Integer(), nullable=False),
        sa.Column("background_path", sa.String(1000), nullable=False),
        sa.Column("preview_path", sa.String(1000)),
        sa.Column("manifest", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_media_templates_key"),
        schema="media",
    )
    op.create_index("ix_media_templates_category", "templates", ["category"], schema="media")
    op.create_index("ix_media_templates_active", "templates", ["is_active"], schema="media")


def downgrade():
    op.drop_index("ix_media_templates_active", table_name="templates", schema="media")
    op.drop_index("ix_media_templates_category", table_name="templates", schema="media")
    op.drop_table("templates", schema="media")
    op.drop_table("settings", schema="media")
