#!/usr/bin/env bash
set -Eeuo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${SHIELDNET_PLUGIN_DIR:-/opt/shieldnet/plugins/verification_level1}"

install -d "$TARGET_DIR"
rsync -a --delete "${SRC_DIR}/" "${TARGET_DIR}/"

ENV_FILE="/etc/shieldnet/backend/migrations.env"
MODE="migration"

if [[ ! -f "$ENV_FILE" ]]; then
  ENV_FILE="/etc/shieldnet/backend/backend.env"
  MODE="backend"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Configuration file not found."
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

if [[ "$MODE" == "migration" ]]; then
  export PGPASSWORD="$SHIELDNET_MIGRATION_DB_PASSWORD"
  DB_HOST="$SHIELDNET_MIGRATION_DB_HOST"
  DB_PORT="$SHIELDNET_MIGRATION_DB_PORT"
  DB_NAME="$SHIELDNET_MIGRATION_DB_NAME"
  DB_USER="$SHIELDNET_MIGRATION_DB_USER"
else
  export PGPASSWORD="$SHIELDNET_DB_PASSWORD"
  DB_HOST="$SHIELDNET_DB_HOST"
  DB_PORT="$SHIELDNET_DB_PORT"
  DB_NAME="$SHIELDNET_DB_NAME"
  DB_USER="$SHIELDNET_DB_USER"
fi

psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -f "$TARGET_DIR/migrations/0001_verification_level1.sql"

systemctl restart shieldnet-backend || true
systemctl restart shieldnet-bot || true

echo "Verification Level 1 installed successfully."
