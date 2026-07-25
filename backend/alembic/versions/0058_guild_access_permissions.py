"""Guild access module permissions compatibility revision.

Revision ID: 0058
Revises: 0057
"""

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Columns permissions and expires_at were already created by revision 0057.
    pass


def downgrade() -> None:
    # Schema changes belong to revision 0057.
    pass
