"""Per-installation Plugin API rate limits.

Revision ID: 0054
Revises: 0053
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_installations",
        sa.Column(
            "rate_limits_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="plugins",
    )

    op.create_check_constraint(
        "ck_plugins_guild_installations_rate_limits_object",
        "guild_installations",
        "jsonb_typeof(rate_limits_json) = 'object'",
        schema="plugins",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_plugins_guild_installations_rate_limits_object",
        "guild_installations",
        schema="plugins",
        type_="check",
    )

    op.drop_column(
        "guild_installations",
        "rate_limits_json",
        schema="plugins",
    )
