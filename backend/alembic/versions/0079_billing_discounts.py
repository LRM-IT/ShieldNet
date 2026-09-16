from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="0079_billing_discounts"
down_revision="0078_global_paid_modules_subscription"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("payments",sa.Column("original_amount_uah",sa.Numeric(12,2)),schema="billing")
    op.add_column("payments",sa.Column("discount_percent",sa.Numeric(5,2),nullable=False,server_default="0"),schema="billing")
    op.add_column("payments",sa.Column("discount_code",sa.String(64)),schema="billing")
    op.create_table("discount_cards",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("code",sa.String(64),nullable=False),sa.Column("percent",sa.Numeric(5,2),nullable=False),sa.Column("active",sa.Boolean(),nullable=False,server_default=sa.text("true")),sa.Column("valid_from",sa.DateTime(timezone=True)),sa.Column("valid_until",sa.DateTime(timezone=True)),sa.Column("max_redemptions",sa.Integer()),sa.Column("redemptions",sa.Integer(),nullable=False,server_default="0"),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint("code",name="uq_billing_discount_card_code"),schema="billing")
    op.create_table("discount_redemptions",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("card_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("guild_id",sa.BigInteger(),nullable=False),sa.Column("redeemed_by_user_id",postgresql.UUID(as_uuid=True)),sa.Column("redeemed_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.ForeignKeyConstraint(["card_id"],["billing.discount_cards.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["guild_id"],["discord.guilds.guild_id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["redeemed_by_user_id"],["core.users.id"],ondelete="SET NULL"),sa.UniqueConstraint("card_id","guild_id",name="uq_billing_discount_redemption_card_guild"),schema="billing")
    op.create_table("tenure_discounts",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("minimum_months",sa.Integer(),nullable=False),sa.Column("percent",sa.Numeric(5,2),nullable=False),sa.Column("active",sa.Boolean(),nullable=False,server_default=sa.text("true")),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint("minimum_months",name="uq_billing_tenure_discount_months"),schema="billing")
    op.execute("INSERT INTO billing.tenure_discounts(id,minimum_months,percent,active) VALUES(gen_random_uuid(),6,5,true),(gen_random_uuid(),12,10,true),(gen_random_uuid(),24,15,true) ON CONFLICT(minimum_months) DO NOTHING")

def downgrade():
    op.drop_table("tenure_discounts",schema="billing")
    op.drop_table("discount_redemptions",schema="billing")
    op.drop_table("discount_cards",schema="billing")
    op.drop_column("payments","discount_code",schema="billing")
    op.drop_column("payments","discount_percent",schema="billing")
    op.drop_column("payments","original_amount_uah",schema="billing")
