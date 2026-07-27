"""Add plugin migration history.

Revision ID: 0060
Revises: 0059
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_migrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("plugin_key", sa.String(96), nullable=False),
        sa.Column("plugin_version", sa.String(40)),
        sa.Column("migration_order", sa.Integer(), nullable=False),
        sa.Column("migration_filename", sa.String(160), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.String(24),
            nullable=False,
            server_default="applied",
        ),
        sa.Column("execution_time_ms", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "plugins.install_jobs.id",
                ondelete="SET NULL",
            ),
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "plugin_key",
            "migration_filename",
            name="uq_plugins_plugin_migrations_key_filename",
        ),
        schema="plugins",
    )

    op.create_index(
        "ix_plugins_plugin_migrations_plugin_key",
        "plugin_migrations",
        ["plugin_key"],
        schema="plugins",
    )
    op.create_index(
        "ix_plugins_plugin_migrations_status",
        "plugin_migrations",
        ["status"],
        schema="plugins",
    )
    op.create_index(
        "ix_plugins_plugin_migrations_job_id",
        "plugin_migrations",
        ["job_id"],
        schema="plugins",
    )
    op.create_index(
        "ix_plugins_plugin_migrations_key_order",
        "plugin_migrations",
        ["plugin_key", "migration_order"],
        schema="plugins",
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM pg_roles
            WHERE rolname = 'shieldnet_backend'
          ) THEN
            GRANT SELECT, INSERT, UPDATE, DELETE
            ON plugins.plugin_migrations
            TO shieldnet_backend;
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_plugins_plugin_migrations_key_order",
        table_name="plugin_migrations",
        schema="plugins",
    )
    op.drop_index(
        "ix_plugins_plugin_migrations_job_id",
        table_name="plugin_migrations",
        schema="plugins",
    )
    op.drop_index(
        "ix_plugins_plugin_migrations_status",
        table_name="plugin_migrations",
        schema="plugins",
    )
    op.drop_index(
        "ix_plugins_plugin_migrations_plugin_key",
        table_name="plugin_migrations",
        schema="plugins",
    )
    op.drop_table("plugin_migrations", schema="plugins")
