from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0076_nbu_exchange_rates"
down_revision = "0075_billing_wallets"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("UPDATE billing.plugin_plans SET currency='UAH'")
    op.create_table("exchange_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("uah_per_unit", sa.Numeric(18,8), nullable=False),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="NBU"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("currency",name="uq_billing_exchange_rate_currency"), schema="billing")

def downgrade():
    op.drop_table("exchange_rates", schema="billing")
