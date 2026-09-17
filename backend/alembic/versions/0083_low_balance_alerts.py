from alembic import op
import sqlalchemy as sa
revision="0083_low_balance_alerts";down_revision="0082_wallet_first_billing";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("wallets",sa.Column("low_balance_enabled",sa.Boolean(),nullable=False,server_default=sa.text("false")),schema="billing")
    op.add_column("wallets",sa.Column("low_balance_threshold",sa.Numeric(14,2),nullable=False,server_default="0"),schema="billing")
def downgrade():
    op.drop_column("wallets","low_balance_threshold",schema="billing");op.drop_column("wallets","low_balance_enabled",schema="billing")
