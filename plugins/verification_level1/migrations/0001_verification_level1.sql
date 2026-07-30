CREATE TABLE IF NOT EXISTS verification_level1_settings (
    guild_id BIGINT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    verification_channel_id BIGINT,
    verified_role_id BIGINT,
    log_channel_id BIGINT,
    nickname_mask VARCHAR(128) NOT NULL DEFAULT '[{ALLIANCE}] {NICKNAME}',
    allow_reverification BOOLEAN NOT NULL DEFAULT TRUE,
    alliance_uppercase BOOLEAN NOT NULL DEFAULT TRUE,
    trim_values BOOLEAN NOT NULL DEFAULT TRUE,
    max_alliance_length INTEGER NOT NULL DEFAULT 16,
    max_nickname_length INTEGER NOT NULL DEFAULT 24,

    verification_message TEXT NOT NULL DEFAULT 'Натисніть кнопку нижче, щоб пройти верифікацію.',
    verification_button_text VARCHAR(80) NOT NULL DEFAULT 'Пройти верифікацію',

    slash_verify_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    slash_verify_name VARCHAR(32) NOT NULL DEFAULT 'verify',
    prefix_verify_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    command_prefix VARCHAR(8) NOT NULL DEFAULT '!',
    prefix_verify_name VARCHAR(32) NOT NULL DEFAULT 'verify',

    slash_rename_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    slash_rename_name VARCHAR(32) NOT NULL DEFAULT 'rename',
    prefix_rename_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    prefix_rename_name VARCHAR(32) NOT NULL DEFAULT 'rename',

    allowed_channel_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    delete_user_command BOOLEAN NOT NULL DEFAULT TRUE,
    cooldown_seconds INTEGER NOT NULL DEFAULT 30,

    assign_role_on_verify BOOLEAN NOT NULL DEFAULT TRUE,
    assign_role_on_rename BOOLEAN NOT NULL DEFAULT TRUE,

    success_message_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    success_message_text TEXT NOT NULL DEFAULT '🎉 {MENTION}, вас успішно верифіковано!',
    success_message_delete_after INTEGER NOT NULL DEFAULT 300,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS verification_level1_members (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    discord_name VARCHAR(255) NOT NULL,
    alliance VARCHAR(64) NOT NULL,
    nickname VARCHAR(64) NOT NULL,
    rendered_nickname VARCHAR(64),
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_by VARCHAR(32) NOT NULL DEFAULT 'self',
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS verification_level1_audit (
    id BIGSERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    actor_user_id BIGINT,
    action VARCHAR(64) NOT NULL,
    old_alliance VARCHAR(64),
    new_alliance VARCHAR(64),
    old_nickname VARCHAR(64),
    new_nickname VARCHAR(64),
    old_rendered_nickname VARCHAR(64),
    new_rendered_nickname VARCHAR(64),
    role_id BIGINT,
    role_assigned BOOLEAN NOT NULL DEFAULT FALSE,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_verification_level1_members_guild
    ON verification_level1_members(guild_id);

CREATE INDEX IF NOT EXISTS ix_verification_level1_audit_guild_created
    ON verification_level1_audit(guild_id, created_at DESC);
