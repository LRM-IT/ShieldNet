"""Change the internal billing base currency from UAH to USD."""
from alembic import op

revision = "0087_usd_billing_base"
down_revision = "0086_wallet_notification_channels"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
    DO $$ DECLARE usd_rate numeric;
    BEGIN
      SELECT uah_per_unit INTO usd_rate FROM billing.exchange_rates WHERE currency='USD' ORDER BY effective_date DESC LIMIT 1;
      IF usd_rate IS NULL OR usd_rate <= 0 THEN RAISE EXCEPTION 'USD exchange rate is required before billing migration'; END IF;
      UPDATE billing.plugin_plans SET monthly_price=round(monthly_price/usd_rate,2), quarterly_price=round(quarterly_price/usd_rate,2), yearly_price=round(yearly_price/usd_rate,2), currency='USD' WHERE currency='UAH';
      UPDATE billing.wallet_transactions t SET amount=round(t.amount/usd_rate,2), balance_after=round(t.balance_after/usd_rate,2) FROM billing.wallets w WHERE t.wallet_id=w.id AND w.currency='UAH';
      UPDATE billing.wallets SET balance=round(balance/usd_rate,2), low_balance_threshold=round(low_balance_threshold/usd_rate,2), currency='USD' WHERE currency='UAH';
      UPDATE billing.discount_cards SET amount_uah=round(amount_uah/usd_rate,2) WHERE amount_uah IS NOT NULL;
      UPDATE billing.payments SET base_amount_uah=round(base_amount_uah/usd_rate,2), original_amount_uah=round(original_amount_uah/usd_rate,2);
    END $$;
    """)
    op.alter_column('plugin_plans','currency',schema='billing',server_default='USD')
    op.alter_column('wallets','currency',schema='billing',server_default='USD')
    op.alter_column('payments','base_amount_uah',new_column_name='base_amount_usd',schema='billing')
    op.alter_column('payments','original_amount_uah',new_column_name='original_amount_usd',schema='billing')
    op.alter_column('discount_cards','amount_uah',new_column_name='amount_usd',schema='billing')

def downgrade():
    raise RuntimeError('USD billing base migration is irreversible')
