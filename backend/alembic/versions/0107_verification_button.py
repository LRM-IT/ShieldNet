"""Optional verification instruction button."""
from alembic import op
import sqlalchemy as sa

revision = "0107_verification_button"
down_revision = "0106_welcome_reminder"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("settings", sa.Column("instruction_button_enabled", sa.Boolean(), nullable=False, server_default=sa.true()), schema="verification")


def downgrade():
    op.drop_column("settings", "instruction_button_enabled", schema="verification")
