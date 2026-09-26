"""Add the client-owned Discord bot subscription plan."""
from alembic import op

revision = "0102_custom_discord_bot"
down_revision = "0101_verification_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO billing.plugin_plans
            (id, plugin_key, is_free, enabled, currency, monthly_price,
             quarterly_price, yearly_price, quarterly_discount_percent,
             yearly_discount_percent)
        VALUES
            (gen_random_uuid(), '__custom_bot__', false, true, 'USD',
             5.00, 14.25, 54.00, 5.00, 10.00)
        ON CONFLICT (plugin_key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM billing.plugin_plans WHERE plugin_key='__custom_bot__'")
