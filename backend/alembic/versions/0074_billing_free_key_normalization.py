from alembic import op

revision = "0074_billing_free_key_normalization"
down_revision = "0073_billing_core"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("UPDATE billing.plugin_plans SET plugin_key='guild_dm_broadcast' WHERE plugin_key='guild-dm-broadcast' AND NOT EXISTS (SELECT 1 FROM billing.plugin_plans WHERE plugin_key='guild_dm_broadcast')")
    op.execute("DELETE FROM billing.plugin_plans WHERE plugin_key='guild-dm-broadcast'")

def downgrade():
    op.execute("UPDATE billing.plugin_plans SET plugin_key='guild-dm-broadcast' WHERE plugin_key='guild_dm_broadcast'")
