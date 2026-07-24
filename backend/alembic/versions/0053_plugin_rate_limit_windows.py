"""Shared Plugin API rate-limit windows.

Revision ID: 0053
Revises: 0052
"""

from alembic import op
import sqlalchemy as sa


revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_windows",
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
            "scope",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "window_started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "request_count",
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
            "guild_id",
            "plugin_key",
            "scope",
            "window_started_at",
            name="pk_plugins_rate_limit_windows",
        ),
        schema="plugins",
    )

    op.create_index(
        "ix_plugins_rate_limit_windows_updated_at",
        "rate_limit_windows",
        ["updated_at"],
        schema="plugins",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_plugins_rate_limit_windows_updated_at",
        table_name="rate_limit_windows",
        schema="plugins",
    )

    op.drop_table(
        "rate_limit_windows",
        schema="plugins",
    )
