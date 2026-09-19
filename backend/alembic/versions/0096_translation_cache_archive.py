"""Add shared persistent translation cache archive."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision="0096_translation_cache_archive";down_revision="0095_billing_delivery_channels";branch_labels=None;depends_on=None

def upgrade():
    op.create_table(
        "translation_cache_archive",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("source_hash",sa.String(64),nullable=False),
        sa.Column("source_text",sa.Text(),nullable=False),
        sa.Column("target_language",sa.String(16),nullable=False),
        sa.Column("protected_terms_hash",sa.String(64),nullable=False,server_default=""),
        sa.Column("translated_text",sa.Text(),nullable=False),
        sa.Column("hit_count",sa.Integer(),nullable=False,server_default="0"),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("last_used_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint("source_hash","target_language","protected_terms_hash",name="uq_translation_archive_lookup"),
        schema="plugins",
    )
    op.create_index("ix_translation_archive_last_used","translation_cache_archive",["last_used_at"],schema="plugins")
    op.create_index("ix_translation_archive_target_language","translation_cache_archive",["target_language"],schema="plugins")

def downgrade():
    op.drop_index("ix_translation_archive_target_language",table_name="translation_cache_archive",schema="plugins")
    op.drop_index("ix_translation_archive_last_used",table_name="translation_cache_archive",schema="plugins")
    op.drop_table("translation_cache_archive",schema="plugins")
