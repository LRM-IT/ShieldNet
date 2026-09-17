"""Remove currency conversion; billing is USD only."""
from alembic import op

revision = "0088_remove_exchange_rates"
down_revision = "0087_usd_billing_base"
branch_labels = None
depends_on = None

def upgrade():
    op.drop_table("exchange_rates", schema="billing")
    op.drop_column("users", "display_currency", schema="core")
    op.drop_column("payments", "fx_rate", schema="billing")

def downgrade():
    raise RuntimeError("USD-only billing migration is irreversible")
