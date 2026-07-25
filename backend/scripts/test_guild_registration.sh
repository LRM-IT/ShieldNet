#!/usr/bin/env bash
set -Eeuo pipefail
TOKEN="$(grep '^SHIELDNET_INTERNAL_SERVICE_TOKEN=' /etc/shieldnet/backend/backend.env|cut -d= -f2-)"
curl -fsS -X POST http://127.0.0.1:8000/api/v1/internal/discord/guilds/register \
-H 'Content-Type: application/json' -H "X-ShieldNet-Service-Token: $TOKEN" \
-d '{"guild_id":100000000000000001,"name":"ShieldNet Test Guild","owner_discord_id":100000000000000002,"member_count":10,"preferred_language":"uk"}'
echo
