# Docker deployment

The Compose stack runs the API, Discord bot, scheduler, plugin worker, plugin runtime manager, plugin watchdog, PostgreSQL, Redis, and the Angular site behind Caddy. Only HTTP port 80 is published on `SHIELDNET_BIND_IP`; the WAF terminates HTTPS. Data lives in named Docker volumes.

1. Install Docker Engine with the Compose plugin on the destination server. Route `guildconsole.lrm-it.com` through the WAF to `SHIELDNET_BIND_IP:80`. TLS terminates at the WAF; the web container listens on HTTP port 80 only.
2. On a new installation, run `python3 docker/init-env.py` and fill the remaining Discord credentials. For a migration, put the approved old configuration under `/root/shieldnet-migration-20260914/extracted/etc/shieldnet` and run `python3 docker/import-legacy-env.py` after initialization. The import retains `AI_CREDENTIALS_MASTER_KEY` and `SHIELDNET_PLUGIN_VAULT_KEY` so encrypted data remains readable. Keep `.env` outside Git and set its permissions to `0600`.
3. Build with `docker compose build` and initialize a new database with `docker compose --profile tools run --rm migrate`. For a migrated database, restore its dump first, then run migrations.
4. Start with `docker compose up -d`. Check `docker compose ps`, `docker compose logs --tail=100 backend`, and `curl https://$SHIELDNET_DOMAIN/api/v1/health/database`.

The old server backup is a PostgreSQL custom-format dump plus an archive containing the existing `/etc/shieldnet` configuration, plugin files, templates, and media assets. Treat both as sensitive. Restore the dump into the new `shieldnet` database using `pg_restore --no-owner --no-acl`; copy plugin, template, and media files into the matching named volumes. Register `https://guildconsole.lrm-it.com/api/v1/auth/discord/callback` in the Discord application settings during cutover. Never run both Discord bot instances with the same token during the switch.

The source repository currently tracks build caches, virtual environments, and old backup files. `.dockerignore` excludes them from image builds, but a separate repository cleanup is needed before relying on compact source-only clones.
