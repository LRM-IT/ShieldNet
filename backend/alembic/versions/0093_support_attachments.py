"""Add image attachments to support ticket messages."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="0093_support_attachments"
down_revision="0092_support_tickets"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("ticket_attachments",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("message_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("support.ticket_messages.id",ondelete="CASCADE"),nullable=False),sa.Column("file_name",sa.String(255),nullable=False),sa.Column("file_path",sa.Text(),nullable=False),sa.Column("mime_type",sa.String(100),nullable=False),sa.Column("file_size",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),schema="support")

def downgrade():
    op.drop_table("ticket_attachments",schema="support")
