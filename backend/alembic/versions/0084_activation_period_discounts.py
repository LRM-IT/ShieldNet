"""Add configurable activation period discounts.

Revision ID: 0084_activation_period_discounts
Revises: 0083_low_balance_alerts
"""
from alembic import op
import sqlalchemy as sa

revision = "0084_activation_period_discounts"
down_revision = "0083_low_balance_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plugin_plans", sa.Column("quarterly_discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"), schema="billing")
    op.add_column("plugin_plans", sa.Column("yearly_discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"), schema="billing")
    op.execute("""
        UPDATE billing.plugin_plans
        SET quarterly_discount_percent = CASE
                WHEN monthly_price > 0 AND quarterly_price IS NOT NULL
                THEN ROUND((1 - quarterly_price / (monthly_price * 3)) * 100, 2)
                ELSE 0 END,
            yearly_discount_percent = CASE
                WHEN monthly_price > 0 AND yearly_price IS NOT NULL
                THEN ROUND((1 - yearly_price / (monthly_price * 12)) * 100, 2)
                ELSE 0 END
        WHERE plugin_key = '__paid_modules__'
    """)


def downgrade() -> None:
    op.drop_column("plugin_plans", "yearly_discount_percent", schema="billing")
    op.drop_column("plugin_plans", "quarterly_discount_percent", schema="billing")
