"""Voting template selection.

Revision ID: 0067_voting_template
Revises: 0066_media_assets
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0067_voting_template"
down_revision = "0066_media_assets"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("voting_polls", sa.Column("result_template_id", postgresql.UUID(as_uuid=True), nullable=True), schema="discord")
    op.add_column("voting_polls", sa.Column("result_language", sa.String(16), nullable=True), schema="discord")
    op.add_column("voting_polls", sa.Column("result_qr_url", sa.String(1000), nullable=True), schema="discord")
    op.add_column("voting_polls", sa.Column("publish_result_image", sa.Boolean(), nullable=False, server_default="true"), schema="discord")
    op.create_foreign_key("fk_voting_polls_result_template", "voting_polls", "templates", ["result_template_id"], ["id"], source_schema="discord", referent_schema="media", ondelete="SET NULL")
    op.create_index("ix_voting_polls_result_template", "voting_polls", ["result_template_id"], schema="discord")


def downgrade():
    op.drop_index("ix_voting_polls_result_template", table_name="voting_polls", schema="discord")
    op.drop_constraint("fk_voting_polls_result_template", "voting_polls", schema="discord", type_="foreignkey")
    op.drop_column("voting_polls", "publish_result_image", schema="discord")
    op.drop_column("voting_polls", "result_qr_url", schema="discord")
    op.drop_column("voting_polls", "result_language", schema="discord")
    op.drop_column("voting_polls", "result_template_id", schema="discord")
