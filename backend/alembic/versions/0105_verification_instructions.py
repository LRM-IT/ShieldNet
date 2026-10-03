"""Verification instructions and cleanup exclusions."""
from alembic import op
import sqlalchemy as sa

revision = "0105_verification_instructions"
down_revision = "0104_subscription_transfers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("settings", sa.Column("instruction_text", sa.Text(), nullable=False, server_default=""), schema="verification")
    op.add_column("settings", sa.Column("cleanup_excluded_message_ids", sa.Text(), nullable=False, server_default=""), schema="verification")


def downgrade():
    op.drop_column("settings", "cleanup_excluded_message_ids", schema="verification")
    op.drop_column("settings", "instruction_text", schema="verification")
