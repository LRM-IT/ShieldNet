"""Add support tickets for bugs and suggestions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0092_support_tickets"
down_revision = "0091_wallet_vouchers"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS support")
    op.create_table("tickets", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False), sa.Column("topic", sa.String(16), nullable=False), sa.Column("subject", sa.String(160), nullable=False), sa.Column("status", sa.String(24), nullable=False, server_default="open"), sa.Column("priority", sa.String(16), nullable=False, server_default="normal"), sa.Column("closed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="support")
    op.create_index("ix_support_tickets_status_updated", "tickets", ["status", "updated_at"], schema="support")
    op.create_table("ticket_messages", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("support.tickets.id", ondelete="CASCADE"), nullable=False), sa.Column("author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id", ondelete="CASCADE"), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="support")
    op.create_index("ix_support_ticket_messages_ticket_created", "ticket_messages", ["ticket_id", "created_at"], schema="support")

def downgrade():
    op.drop_table("ticket_messages", schema="support"); op.drop_table("tickets", schema="support"); op.execute("DROP SCHEMA IF EXISTS support")
