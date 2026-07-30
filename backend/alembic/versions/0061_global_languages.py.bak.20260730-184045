"""Global language directory.

Revision ID: 0061_global_languages
Revises: 0060_voting_plugin
"""
from alembic import op
import sqlalchemy as sa

revision = "0061_global_languages"
down_revision = "0060_voting_plugin"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "global_languages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("native_name", sa.String(120), nullable=False),
        sa.Column("flag", sa.String(16)),
        sa.Column("locale", sa.String(32)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_global_languages"),
        sa.UniqueConstraint("code", name="uq_platform_global_languages_code"),
        schema="platform",
    )
    op.create_index(
        "ix_platform_global_languages_code",
        "global_languages",
        ["code"],
        schema="platform",
    )
    op.execute("""
      INSERT INTO platform.global_languages
        (code,name,native_name,flag,locale,is_active,sort_order)
      VALUES
        ('en','English','English','🇬🇧','en-US',true,10),
        ('uk','Ukrainian','Українська','🇺🇦','uk-UA',true,20),
        ('ru','Russian','Русский','🇷🇺','ru-RU',true,30),
        ('de','German','Deutsch','🇩🇪','de-DE',true,40),
        ('fr','French','Français','🇫🇷','fr-FR',true,50),
        ('es','Spanish','Español','🇪🇸','es-ES',true,60),
        ('it','Italian','Italiano','🇮🇹','it-IT',true,70),
        ('pl','Polish','Polski','🇵🇱','pl-PL',true,80),
        ('pt','Portuguese','Português','🇵🇹','pt-PT',true,90),
        ('tr','Turkish','Türkçe','🇹🇷','tr-TR',true,100),
        ('ja','Japanese','日本語','🇯🇵','ja-JP',true,110),
        ('ko','Korean','한국어','🇰🇷','ko-KR',true,120),
        ('zh','Chinese','中文','🇨🇳','zh-CN',true,130),
        ('vi','Vietnamese','Tiếng Việt','🇻🇳','vi-VN',true,140),
        ('ar','Arabic','العربية','🇸🇦','ar-SA',true,150),
        ('th','Thai','ไทย','🇹🇭','th-TH',true,160),
        ('id','Indonesian','Bahasa Indonesia','🇮🇩','id-ID',true,170)
      ON CONFLICT (code) DO NOTHING
    """)
    op.execute("""
      DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='shieldnet_backend') THEN
          GRANT SELECT,INSERT,UPDATE,DELETE
          ON platform.global_languages
          TO shieldnet_backend;
          GRANT USAGE,SELECT,UPDATE
          ON ALL SEQUENCES IN SCHEMA platform
          TO shieldnet_backend;
        END IF;
      END $$;
    """)


def downgrade():
    op.drop_index(
        "ix_platform_global_languages_code",
        table_name="global_languages",
        schema="platform",
    )
    op.drop_table("global_languages", schema="platform")
