from alembic import op

revision = "0078_global_paid_modules_subscription"
down_revision = "0077_payment_currency_quotes"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
    INSERT INTO billing.plugin_plans(id,plugin_key,is_free,enabled,currency,monthly_price,quarterly_price,yearly_price)
    VALUES(gen_random_uuid(),'__paid_modules__',false,true,'UAH',49,129,449)
    ON CONFLICT(plugin_key) DO NOTHING
    """)
    op.execute("""
    INSERT INTO billing.subscriptions(id,guild_id,plugin_key,status,billing_period,starts_at,expires_at,provider,external_order_id,created_at,updated_at)
    SELECT gen_random_uuid(),guild_id,'__paid_modules__','active','migrated',min(starts_at),max(expires_at),'migration',NULL,now(),now()
    FROM billing.subscriptions WHERE status='active' AND plugin_key<>'__paid_modules__' GROUP BY guild_id
    ON CONFLICT(guild_id,plugin_key) DO UPDATE SET expires_at=GREATEST(billing.subscriptions.expires_at,EXCLUDED.expires_at),status='active'
    """)
    op.execute("UPDATE billing.subscriptions SET status='migrated' WHERE status='active' AND plugin_key<>'__paid_modules__'")

def downgrade():
    op.execute("DELETE FROM billing.subscriptions WHERE plugin_key='__paid_modules__' AND provider='migration'")
    op.execute("DELETE FROM billing.plugin_plans WHERE plugin_key='__paid_modules__'")
