"""Template Bank game hierarchy.

Revision ID: 0065_template_games
Revises: 0064_template_bank
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0065_template_games"
down_revision = "0064_template_bank"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "game_libraries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("icon_path", sa.String(1000)),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_media_game_libraries_key"),
        schema="media",
    )
    op.add_column(
        "templates",
        sa.Column("game_library_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="media",
    )
    op.create_foreign_key(
        "fk_media_templates_game_library",
        "templates", "game_libraries",
        ["game_library_id"], ["id"],
        source_schema="media", referent_schema="media",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_media_templates_game_library",
        "templates", ["game_library_id"],
        schema="media",
    )
    op.execute("""
      INSERT INTO media.settings
        (id, default_qr_url, default_qr_caption, allow_guild_qr_override)
      VALUES
        (1, 'https://discord.lrm-it.com', 'Visit our website', false)
      ON CONFLICT (id) DO NOTHING
    """)

def downgrade():
    op.drop_index("ix_media_templates_game_library", table_name="templates", schema="media")
    op.drop_constraint("fk_media_templates_game_library", "templates", schema="media", type_="foreignkey")
    op.drop_column("templates", "game_library_id", schema="media")
    op.drop_table("game_libraries", schema="media")
