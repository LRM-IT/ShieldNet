from alembic import op
import sqlalchemy as sa

revision = "0082_wallet_first_billing"
down_revision = "0081_rename_voting_plugin"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("subscriptions", sa.Column("owner_discord_id", sa.BigInteger()), schema="billing")
    op.add_column("subscriptions", sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("false")), schema="billing")
    op.add_column("payments", sa.Column("purpose", sa.String(24), nullable=False, server_default="subscription"), schema="billing")
    op.add_column("payments", sa.Column("owner_discord_id", sa.BigInteger()), schema="billing")
    op.alter_column("payments", "guild_id", nullable=True, schema="billing")
    op.alter_column("payments", "plugin_key", nullable=True, schema="billing")
    op.alter_column("payments", "billing_period", nullable=True, schema="billing")
    op.execute("UPDATE billing.subscriptions s SET owner_discord_id=g.owner_discord_id FROM discord.guilds g WHERE g.guild_id=s.guild_id AND g.owner_discord_id>0")

def downgrade():
    op.execute("DELETE FROM billing.payments WHERE guild_id IS NULL OR plugin_key IS NULL OR billing_period IS NULL")
    op.alter_column("payments", "billing_period", nullable=False, schema="billing")
    op.alter_column("payments", "plugin_key", nullable=False, schema="billing")
    op.alter_column("payments", "guild_id", nullable=False, schema="billing")
    op.drop_column("payments", "owner_discord_id", schema="billing")
    op.drop_column("payments", "purpose", schema="billing")
    op.drop_column("subscriptions", "auto_renew", schema="billing")
    op.drop_column("subscriptions", "owner_discord_id", schema="billing")
