"""Disable automatic renewal for existing server subscriptions."""

from alembic import op


revision = "0098_disable_subscription_auto_renew"
down_revision = "0097_translation_archive_source_language"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE billing.subscriptions SET auto_renew = false WHERE auto_renew = true")


def downgrade():
    pass
