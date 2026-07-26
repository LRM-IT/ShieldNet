CREATE SCHEMA IF NOT EXISTS plugin_system AUTHORIZATION shieldnet_owner;

CREATE TABLE IF NOT EXISTS plugin_system.migrations (
    plugin_key VARCHAR(96) NOT NULL,
    migration_name VARCHAR(255) NOT NULL,
    checksum_sha256 VARCHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (plugin_key, migration_name)
);

ALTER SCHEMA plugin_system OWNER TO shieldnet_owner;
ALTER TABLE plugin_system.migrations OWNER TO shieldnet_owner;

GRANT USAGE ON SCHEMA plugin_system TO shieldnet_backend;
GRANT SELECT ON plugin_system.migrations TO shieldnet_backend;
