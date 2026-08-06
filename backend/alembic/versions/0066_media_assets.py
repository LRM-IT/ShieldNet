"""Media Asset Library.

Revision ID: 0066_media_assets
Revises: 0065_template_games
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0066_media_assets"
down_revision = "0065_template_games"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(140), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("asset_type", sa.String(40), nullable=False),
        sa.Column("game_library_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("preview_path", sa.String(1000)),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_media_assets_key"),
        sa.ForeignKeyConstraint(
            ["game_library_id"], ["media.game_libraries.id"],
            name="fk_media_assets_game_library", ondelete="SET NULL",
        ),
        schema="media",
    )
    op.create_index("ix_media_assets_type", "assets", ["asset_type"], schema="media")
    op.create_index("ix_media_assets_game", "assets", ["game_library_id"], schema="media")
    op.create_index("ix_media_assets_active", "assets", ["is_active"], schema="media")

def downgrade():
    op.drop_index("ix_media_assets_active", table_name="assets", schema="media")
    op.drop_index("ix_media_assets_game", table_name="assets", schema="media")
    op.drop_index("ix_media_assets_type", table_name="assets", schema="media")
    op.drop_table("assets", schema="media")
