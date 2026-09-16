"""Multiple match criteria per verification level."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0072_verification_level_criteria"
down_revision = "0071_verification_levels"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("levels", sa.Column("criteria", postgresql.JSONB(), nullable=False, server_default="[]"), schema="verification")
    op.execute("""UPDATE verification.levels SET criteria = jsonb_build_array(jsonb_build_object('label','Основна ознака','expected_text',expected_text,'role_ids',role_ids)) WHERE expected_text <> ''""")

def downgrade():
    op.drop_column("levels", "criteria", schema="verification")
