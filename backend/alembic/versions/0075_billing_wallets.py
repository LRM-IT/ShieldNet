from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0075_billing_wallets"
down_revision = "0074_billing_free_key_normalization"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("balance", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="UAH"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("discord_user_id","currency",name="uq_billing_wallet_owner_currency"), schema="billing")
    op.create_table("wallet_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(14,2), nullable=False),
        sa.Column("balance_after", sa.Numeric(14,2), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True)),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["wallet_id"],["billing.wallets.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"],["billing.payments.id"],ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"],["core.users.id"],ondelete="SET NULL"), schema="billing")
    op.create_index("ix_billing_wallet_transactions_wallet", "wallet_transactions", ["wallet_id","created_at"], schema="billing")

def downgrade():
    op.drop_table("wallet_transactions", schema="billing")
    op.drop_table("wallets", schema="billing")
