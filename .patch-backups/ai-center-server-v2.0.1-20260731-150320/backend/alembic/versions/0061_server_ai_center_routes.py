"""server scoped AI Center routes and failover

Revision ID: 0061_server_ai_center_routes
Revises: 0060_voting_plugin
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0061_server_ai_center_routes"
down_revision = "0060_voting_plugin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False), schema="ai")
    op.add_column("providers", sa.Column("circuit_open_until", sa.DateTime(timezone=True), nullable=True), schema="ai")

    op.create_table(
        "routes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("capability", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("max_total_attempts", sa.Integer(), server_default="6", nullable=False),
        sa.Column("failure_threshold", sa.Integer(), server_default="3", nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), server_default="120", nullable=False),
        sa.Column("configuration", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["discord.guilds.guild_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("guild_id", "capability", name="uq_ai_route_guild_capability"),
        schema="ai",
    )
    op.create_index("ix_ai_routes_guild_id", "routes", ["guild_id"], schema="ai")

    op.create_table(
        "route_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("retries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("configuration", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["ai.routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["ai.providers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("route_id", "position", name="uq_ai_route_target_position"),
        schema="ai",
    )
    op.create_index("ix_ai_route_targets_route_id", "route_targets", ["route_id"], schema="ai")
    op.create_index("ix_ai_route_targets_provider_id", "route_targets", ["provider_id"], schema="ai")

    # Convert existing per-plugin settings into server capability routes.
    op.execute("""
    INSERT INTO ai.routes (id, guild_id, capability, enabled, configuration)
    SELECT gen_random_uuid(), guild_id, capability, bool_or(enabled), '{}'::jsonb
    FROM ai.module_settings
    GROUP BY guild_id, capability
    ON CONFLICT (guild_id, capability) DO NOTHING
    """)
    op.execute("""
    INSERT INTO ai.route_targets (id, route_id, provider_id, position, model, retries, enabled, configuration)
    SELECT gen_random_uuid(), r.id, x.provider_id,
           row_number() OVER (PARTITION BY r.id ORDER BY x.priority, x.provider_id),
           x.model, 0, true, '{}'::jsonb
    FROM ai.routes r
    JOIN (
      SELECT guild_id, capability, provider_id, min(model) AS model, 1 AS priority
      FROM ai.module_settings WHERE provider_id IS NOT NULL
      GROUP BY guild_id, capability, provider_id
    ) x ON x.guild_id=r.guild_id AND x.capability=r.capability
    ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("ix_ai_route_targets_provider_id", table_name="route_targets", schema="ai")
    op.drop_index("ix_ai_route_targets_route_id", table_name="route_targets", schema="ai")
    op.drop_table("route_targets", schema="ai")
    op.drop_index("ix_ai_routes_guild_id", table_name="routes", schema="ai")
    op.drop_table("routes", schema="ai")
    op.drop_column("providers", "circuit_open_until", schema="ai")
    op.drop_column("providers", "consecutive_failures", schema="ai")
