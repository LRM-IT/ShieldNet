"""Plugin Runtime daily usage aggregates.

Revision ID: 0055
Revises: 0054
"""

from alembic import op
import sqlalchemy as sa


revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_daily",
        sa.Column(
            "day",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "guild_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "plugin_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "requests",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "successful",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "errors",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "rate_limited",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "duration_total_ms",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "maximum_duration_ms",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint(
            "day",
            "guild_id",
            "plugin_key",
            name="pk_plugins_usage_daily",
        ),
        schema="plugins",
    )

    op.create_index(
        "ix_plugins_usage_daily_plugin_day",
        "usage_daily",
        [
            "guild_id",
            "plugin_key",
            "day",
        ],
        schema="plugins",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_plugins_usage_daily_plugin_day",
        table_name="usage_daily",
        schema="plugins",
    )

    op.drop_table(
        "usage_daily",
        schema="plugins",
    )
