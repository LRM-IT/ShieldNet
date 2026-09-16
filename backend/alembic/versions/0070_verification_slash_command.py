"""Custom verification slash command.

Revision ID: 0070_verification_slash_command
Revises: 0069_verification_invocation
"""
from alembic import op
import sqlalchemy as sa

revision = "0070_verification_slash_command"
down_revision = "0069_verification_invocation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("settings", sa.Column("slash_command_name", sa.String(32), nullable=False, server_default="verify"), schema="verification")


def downgrade():
    op.drop_column("settings", "slash_command_name", schema="verification")
