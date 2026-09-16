from alembic import op
import sqlalchemy as sa

revision = "0077_payment_currency_quotes"
down_revision = "0076_nbu_exchange_rates"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("payments", sa.Column("base_amount_uah", sa.Numeric(12,2)), schema="billing")
    op.add_column("payments", sa.Column("fx_rate", sa.Numeric(18,8)), schema="billing")
    op.add_column("payments", sa.Column("quote_expires_at", sa.DateTime(timezone=True)), schema="billing")
    op.execute("UPDATE billing.payments SET base_amount_uah=amount WHERE currency='UAH'")

def downgrade():
    op.drop_column("payments", "quote_expires_at", schema="billing")
    op.drop_column("payments", "fx_rate", schema="billing")
    op.drop_column("payments", "base_amount_uah", schema="billing")
