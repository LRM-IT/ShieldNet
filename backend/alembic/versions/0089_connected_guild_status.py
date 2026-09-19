"""Treat bot-synchronized guilds as connected without requiring setup wizard."""

from alembic import op


revision = "0089_connected_guild_status"
down_revision = "0088_remove_exchange_rates"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE discord.guilds
        SET status = 'active'
        WHERE status = 'need_setup'
          AND last_sync_at IS NOT NULL
          AND bot_status = 'online'
        """
    )
    op.execute(
        "ALTER TABLE discord.guilds ALTER COLUMN status SET DEFAULT 'inactive'"
    )


def downgrade():
    op.execute(
        "ALTER TABLE discord.guilds ALTER COLUMN status SET DEFAULT 'need_setup'"
    )
