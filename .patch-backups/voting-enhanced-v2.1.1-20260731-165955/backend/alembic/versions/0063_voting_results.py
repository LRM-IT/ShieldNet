"""Voting localization, automatic close and result presentation settings.

Revision ID: 0063_voting_results
Revises: 0062_server_ai_center_routes
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0063_voting_results"
down_revision = "0062_server_ai_center_routes"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "voting_polls",
        sa.Column("result_settings", postgresql.JSONB(), nullable=False, server_default="{}"),
        schema="discord",
    )
    op.add_column(
        "voting_polls",
        sa.Column("result_message_id", sa.BigInteger(), nullable=True),
        schema="discord",
    )

def downgrade():
    op.drop_column("voting_polls", "result_message_id", schema="discord")
    op.drop_column("voting_polls", "result_settings", schema="discord")
