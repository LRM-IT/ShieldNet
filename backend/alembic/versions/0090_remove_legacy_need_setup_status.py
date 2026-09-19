"""Remove the legacy setup-dependent status from existing guild records."""

from alembic import op


revision = "0090_remove_legacy_need_setup_status"
down_revision = "0089_connected_guild_status"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE discord.guilds
        SET status = CASE
            WHEN bot_status = 'online' THEN 'active'::discord.guild_status
            ELSE 'inactive'::discord.guild_status
        END
        WHERE status = 'need_setup'
        """
    )


def downgrade():
    pass
