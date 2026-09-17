from alembic import op
import sqlalchemy as sa

revision = "0080_fixed_amount_vouchers"
down_revision = "0079_billing_discounts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "discount_cards",
        sa.Column("discount_type", sa.String(16), nullable=False, server_default="percent"),
        schema="billing",
    )
    op.add_column(
        "discount_cards",
        sa.Column("amount_uah", sa.Numeric(12, 2), nullable=True),
        schema="billing",
    )


def downgrade():
    op.drop_column("discount_cards", "amount_uah", schema="billing")
    op.drop_column("discount_cards", "discount_type", schema="billing")
