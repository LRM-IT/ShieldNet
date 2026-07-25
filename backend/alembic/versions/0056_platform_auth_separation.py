"""platform auth separation

Revision ID: 0056
Revises: 0055
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("sessions", sa.Column("auth_source", sa.String(length=32), nullable=False, server_default="discord_guild"), schema="core")
    op.create_table("platform_discord_admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="platform_admin"),
        sa.Column("display_name", sa.String(length=128)),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.users.id", ondelete="SET NULL")),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("discord_user_id", name="uq_core_platform_discord_admins_discord_user_id"),
        schema="core")
    op.create_index("ix_core_platform_discord_admins_active", "platform_discord_admins", ["is_active"], schema="core")

def downgrade():
    op.drop_index("ix_core_platform_discord_admins_active", table_name="platform_discord_admins", schema="core")
    op.drop_table("platform_discord_admins", schema="core")
    op.drop_column("sessions", "auth_source", schema="core")
