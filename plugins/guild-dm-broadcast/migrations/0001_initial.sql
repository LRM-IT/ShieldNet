CREATE SCHEMA IF NOT EXISTS plugin_guild_dm_broadcast AUTHORIZATION shieldnet_owner;

CREATE TABLE IF NOT EXISTS plugin_guild_dm_broadcast.settings (
    guild_id BIGINT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    max_recipients INTEGER NOT NULL DEFAULT 1000,
    cooldown_minutes INTEGER NOT NULL DEFAULT 30,
    batch_size INTEGER NOT NULL DEFAULT 10,
    delay_between_batches_seconds INTEGER NOT NULL DEFAULT 5,
    default_locale VARCHAR(16) NOT NULL DEFAULT 'en',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plugin_guild_dm_broadcast.broadcasts (
    id UUID PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    created_by UUID NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    audience_filter JSONB NOT NULL DEFAULT '{}'::jsonb,
    default_locale VARCHAR(16) NOT NULL DEFAULT 'en',
    recipient_count INTEGER NOT NULL DEFAULT 0,
    sent_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plugin_guild_dm_broadcast.messages (
    id UUID PRIMARY KEY,
    broadcast_id UUID NOT NULL REFERENCES plugin_guild_dm_broadcast.broadcasts(id) ON DELETE CASCADE,
    locale VARCHAR(16) NOT NULL,
    title VARCHAR(256),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (broadcast_id, locale)
);

CREATE TABLE IF NOT EXISTS plugin_guild_dm_broadcast.deliveries (
    id UUID PRIMARY KEY,
    broadcast_id UUID NOT NULL REFERENCES plugin_guild_dm_broadcast.broadcasts(id) ON DELETE CASCADE,
    guild_id BIGINT NOT NULL,
    discord_user_id BIGINT NOT NULL,
    locale VARCHAR(16) NOT NULL DEFAULT 'en',
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (broadcast_id, discord_user_id)
);

ALTER SCHEMA plugin_guild_dm_broadcast OWNER TO shieldnet_owner;
ALTER TABLE plugin_guild_dm_broadcast.settings OWNER TO shieldnet_owner;
ALTER TABLE plugin_guild_dm_broadcast.broadcasts OWNER TO shieldnet_owner;
ALTER TABLE plugin_guild_dm_broadcast.messages OWNER TO shieldnet_owner;
ALTER TABLE plugin_guild_dm_broadcast.deliveries OWNER TO shieldnet_owner;

GRANT USAGE ON SCHEMA plugin_guild_dm_broadcast TO shieldnet_backend;
GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA plugin_guild_dm_broadcast TO shieldnet_backend;
