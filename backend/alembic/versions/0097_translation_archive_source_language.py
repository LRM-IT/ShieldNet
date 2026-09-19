"""Separate shared translations by detected source language."""
from alembic import op
import sqlalchemy as sa

revision="0097_translation_archive_source_language";down_revision="0096_translation_cache_archive";branch_labels=None;depends_on=None

def upgrade():
    op.drop_constraint("uq_translation_archive_lookup","translation_cache_archive",schema="plugins",type_="unique")
    op.add_column("translation_cache_archive",sa.Column("source_language",sa.String(16),nullable=False,server_default="auto"),schema="plugins")
    op.create_unique_constraint("uq_translation_archive_lookup","translation_cache_archive",["source_hash","source_language","target_language","protected_terms_hash"],schema="plugins")

def downgrade():
    op.drop_constraint("uq_translation_archive_lookup","translation_cache_archive",schema="plugins",type_="unique")
    op.drop_column("translation_cache_archive","source_language",schema="plugins")
    op.create_unique_constraint("uq_translation_archive_lookup","translation_cache_archive",["source_hash","target_language","protected_terms_hash"],schema="plugins")
