BEGIN;

CREATE TABLE IF NOT EXISTS discord.guild_languages (
    id              BIGSERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL REFERENCES discord.guilds(guild_id) ON DELETE CASCADE,
    language_code   VARCHAR(16) NOT NULL REFERENCES platform.global_languages(code) ON DELETE CASCADE,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    is_primary      BOOLEAN NOT NULL DEFAULT FALSE,
    is_fallback     BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order      INTEGER NOT NULL DEFAULT 100,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_discord_guild_languages_guild_code UNIQUE (guild_id, language_code)
);

CREATE INDEX IF NOT EXISTS ix_discord_guild_languages_guild
    ON discord.guild_languages(guild_id, enabled, sort_order);

CREATE UNIQUE INDEX IF NOT EXISTS uq_discord_guild_languages_primary
    ON discord.guild_languages(guild_id)
    WHERE is_primary IS TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_discord_guild_languages_fallback
    ON discord.guild_languages(guild_id)
    WHERE is_fallback IS TRUE;

COMMIT;
