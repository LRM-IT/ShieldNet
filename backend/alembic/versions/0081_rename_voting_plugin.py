from alembic import op

revision = "0081_rename_voting_plugin"
down_revision = "0080_fixed_amount_vouchers"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE plugins.registry SET name = 'Voting' WHERE plugin_key = 'voting'")
    op.execute("UPDATE plugins.marketplace_items SET name = 'Voting' WHERE plugin_key = 'voting'")


def downgrade():
    op.execute("UPDATE plugins.registry SET name = 'ShieldNet Voting' WHERE plugin_key = 'voting'")
    op.execute("UPDATE plugins.marketplace_items SET name = 'ShieldNet Voting' WHERE plugin_key = 'voting'")
