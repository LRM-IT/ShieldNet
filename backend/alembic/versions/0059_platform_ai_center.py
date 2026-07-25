"""Platform AI Center.

Revision ID: 0059
Revises: 0058
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("api_base_url", sa.String(length=500), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(length=32), nullable=True),
        sa.Column("organization_id", sa.String(length=255), nullable=True),
        sa.Column("project_id", sa.String(length=255), nullable=True),
        sa.Column("default_model", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="30", nullable=False),
        sa.Column("max_retries", sa.Integer(), server_default="2", nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("last_health_status", sa.String(length=32), nullable=True),
        sa.Column("last_health_latency_ms", sa.Integer(), nullable=True),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["core.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_ai_platform_provider_name"),
        schema="ai",
    )

    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("defaults", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("limits", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("emergency_stop", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["core.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="ai",
    )


def downgrade() -> None:
    op.drop_table("platform_settings", schema="ai")
    op.drop_table("platform_providers", schema="ai")
