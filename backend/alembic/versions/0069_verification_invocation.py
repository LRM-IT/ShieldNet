"""Verification server number and invocation settings.

Revision ID: 0069_verification_invocation
Revises: 0068_first_introduction
"""
from alembic import op
import sqlalchemy as sa

revision = "0069_verification_invocation"
down_revision = "0068_first_introduction"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("settings", sa.Column("invocation_channel_id", sa.BigInteger(), nullable=True), schema="verification")
    op.add_column("settings", sa.Column("text_commands", sa.String(255), nullable=False, server_default="!verify"), schema="verification")
    op.add_column("requests", sa.Column("server_number", sa.String(32), nullable=False, server_default=""), schema="verification")


def downgrade():
    op.drop_column("requests", "server_number", schema="verification")
    op.drop_column("settings", "text_commands", schema="verification")
    op.drop_column("settings", "invocation_channel_id", schema="verification")
