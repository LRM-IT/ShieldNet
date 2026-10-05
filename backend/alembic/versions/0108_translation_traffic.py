"""Persist deduplicated incoming translation messages."""
from alembic import op
import sqlalchemy as sa
revision = "0108_translation_traffic"
down_revision = "0107_verification_button"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("translation_incoming",
        sa.Column("guild_id",sa.BigInteger(),sa.ForeignKey("discord.guilds.guild_id",ondelete="CASCADE"),primary_key=True),
        sa.Column("message_id",sa.BigInteger(),primary_key=True),
        sa.Column("channel_id",sa.BigInteger(),nullable=False),
        sa.Column("received_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),schema="discord")
    op.create_index("ix_translation_incoming_guild_channel_time","translation_incoming",["guild_id","channel_id","received_at"],schema="discord")

def downgrade():
    op.drop_table("translation_incoming",schema="discord")
