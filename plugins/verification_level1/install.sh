#!/usr/bin/env bash
set -Eeuo pipefail
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${SHIELDNET_PLUGINS_ROOT:-/opt/shieldnet/plugins}"
TARGET_DIR="${PLUGIN_ROOT}/verification_level1"
BACKEND_SERVICE="${SHIELDNET_BACKEND_SERVICE:-shieldnet-backend}"
BOT_SERVICE="${SHIELDNET_BOT_SERVICE:-shieldnet-bot}"
echo "[1/6] Validating plugin package"
python3 -m json.tool "${SRC_DIR}/plugin.json" >/dev/null
test -f "${SRC_DIR}/runtime.py"
test -f "${SRC_DIR}/migrations/0001_verification_level1.sql"
echo "[2/6] Installing into ${TARGET_DIR}"
install -d -m 0755 "${TARGET_DIR}"
rsync -a --delete --exclude='.git' --exclude='__pycache__' "${SRC_DIR}/" "${TARGET_DIR}/"
echo "[3/6] Installing Python requirements"
if [[ -x /opt/shieldnet/backend/.venv/bin/pip ]]; then /opt/shieldnet/backend/.venv/bin/pip install -r "${TARGET_DIR}/requirements.txt"; elif [[ -x /opt/shieldnet/venv/bin/pip ]]; then /opt/shieldnet/venv/bin/pip install -r "${TARGET_DIR}/requirements.txt"; else python3 -m pip install -r "${TARGET_DIR}/requirements.txt"; fi
ENV_FILE=/etc/shieldnet/backend/migrations.env; MODE=migration
if [[ ! -f "$ENV_FILE" ]]; then ENV_FILE=/etc/shieldnet/backend/backend.env; MODE=backend; fi
[[ -f "$ENV_FILE" ]] || { echo 'ERROR: database configuration not found'; exit 1; }
set -a; source "$ENV_FILE"; set +a
if [[ "$MODE" == migration ]]; then export PGPASSWORD="$SHIELDNET_MIGRATION_DB_PASSWORD"; DB_HOST="$SHIELDNET_MIGRATION_DB_HOST"; DB_PORT="$SHIELDNET_MIGRATION_DB_PORT"; DB_NAME="$SHIELDNET_MIGRATION_DB_NAME"; DB_USER="$SHIELDNET_MIGRATION_DB_USER"; else export PGPASSWORD="$SHIELDNET_DB_PASSWORD"; DB_HOST="$SHIELDNET_DB_HOST"; DB_PORT="$SHIELDNET_DB_PORT"; DB_NAME="$SHIELDNET_DB_NAME"; DB_USER="$SHIELDNET_DB_USER"; fi
echo "[4/6] Applying PostgreSQL migration"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "${TARGET_DIR}/migrations/0001_verification_level1.sql"
echo "[5/6] Restarting ShieldNet services"
systemctl restart "$BACKEND_SERVICE"
systemctl restart "$BOT_SERVICE"
echo "[6/6] Done. Open Plugin Platform and press Scan plugin directory."
