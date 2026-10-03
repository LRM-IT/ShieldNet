"""Separate welcome and reminder message templates."""
from alembic import op
import sqlalchemy as sa

revision = "0106_welcome_reminder"
down_revision = "0105_verification_instructions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("settings", sa.Column("reminder_template", sa.Text(), nullable=False,
        server_default='⏰ Verification reminder, {mention}!\n\nYou have not completed verification yet. Please go to {verification_channel} and use the verification command to submit your details.\n\nComplete verification to access **{guild}**. If you need help, contact a moderator.'), schema="plugin_welcome")


def downgrade():
    op.drop_column("settings", "reminder_template", schema="plugin_welcome")
