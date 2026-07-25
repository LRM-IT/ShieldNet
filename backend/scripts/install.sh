#!/usr/bin/env bash
set -Eeuo pipefail

APP_USER="shieldnet-api"
APP_GROUP="shieldnet-api"
APP_DIR="/opt/shieldnet/backend"
CONFIG_DIR="/etc/shieldnet/backend"
LOG_DIR="/var/log/shieldnet/backend"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root."
  exit 1
fi

source /etc/shieldnet/database-secrets.env
: "${SHIELDNET_BACKEND_PASSWORD:?Missing SHIELDNET_BACKEND_PASSWORD}"
: "${SHIELDNET_OWNER_PASSWORD:?Missing SHIELDNET_OWNER_PASSWORD}"

if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /sbin/nologin "$APP_USER"
fi

mkdir -p "$APP_DIR" "$CONFIG_DIR" "$LOG_DIR"

if [[ -d "$APP_DIR/app" ]]; then
  BACKUP="/var/backups/shieldnet/backend-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$BACKUP"
  rsync -a "$APP_DIR/" "$BACKUP/"
  echo "Previous backend saved to $BACKUP"
fi

rsync -a --delete \
  --exclude 'venv' \
  --exclude '.git' \
  "$SOURCE_DIR/" "$APP_DIR/"

rm -rf "$APP_DIR/venv"
python3 -m venv "$APP_DIR/venv"

"$APP_DIR/venv/bin/pip" install --upgrade pip setuptools wheel
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ -f "$CONFIG_DIR/backend.env" ]]; then
  SECRET_KEY="$(grep '^SHIELDNET_SECRET_KEY=' "$CONFIG_DIR/backend.env" | cut -d= -f2-)"
fi
SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 64)}"
INTERNAL_TOKEN="$(openssl rand -hex 48)"

cat > "$CONFIG_DIR/backend.env" <<EOF
SHIELDNET_ENV=development
SHIELDNET_DEBUG=false
SHIELDNET_API_HOST=127.0.0.1
SHIELDNET_API_PORT=8000
SHIELDNET_API_WORKERS=1
SHIELDNET_SECRET_KEY=${SECRET_KEY}
SHIELDNET_INTERNAL_SERVICE_TOKEN=${INTERNAL_TOKEN}
SHIELDNET_JWT_ALGORITHM=HS256
SHIELDNET_ACCESS_TOKEN_MINUTES=15
SHIELDNET_REFRESH_TOKEN_DAYS=30
SHIELDNET_DB_HOST=127.0.0.1
SHIELDNET_DB_PORT=5432
SHIELDNET_DB_NAME=shieldnet
SHIELDNET_DB_USER=shieldnet_backend
SHIELDNET_DB_PASSWORD=${SHIELDNET_BACKEND_PASSWORD}
SHIELDNET_DB_POOL_SIZE=10
SHIELDNET_DB_MAX_OVERFLOW=20
SHIELDNET_DB_POOL_TIMEOUT=30
SHIELDNET_DEFAULT_LANGUAGE=uk
SHIELDNET_TIMEZONE=Europe/Kyiv
SHIELDNET_LOG_LEVEL=INFO
EOF

cat > "$CONFIG_DIR/migrations.env" <<EOF
SHIELDNET_MIGRATION_DB_HOST=127.0.0.1
SHIELDNET_MIGRATION_DB_PORT=5432
SHIELDNET_MIGRATION_DB_NAME=shieldnet
SHIELDNET_MIGRATION_DB_USER=shieldnet_owner
SHIELDNET_MIGRATION_DB_PASSWORD=${SHIELDNET_OWNER_PASSWORD}
EOF

chown -R "$APP_USER:$APP_GROUP" "$APP_DIR" "$LOG_DIR"
chown root:"$APP_GROUP" /etc/shieldnet "$CONFIG_DIR"
chmod 750 /etc/shieldnet "$CONFIG_DIR"
chmod 640 "$CONFIG_DIR/backend.env" "$CONFIG_DIR/migrations.env"

find "$APP_DIR/app" -type d -exec chmod 750 {} \;
find "$APP_DIR/app" -type f -exec chmod 640 {} \;
find "$APP_DIR/alembic" -type d -exec chmod 750 {} \;
find "$APP_DIR/alembic" -type f -exec chmod 640 {} \;
chmod 640 "$APP_DIR/requirements.txt" "$APP_DIR/alembic.ini"
find "$APP_DIR/venv/bin" -maxdepth 1 -type f -exec chmod 755 {} \;

install -m 0644 "$APP_DIR/deploy/shieldnet-backend.service" \
  /etc/systemd/system/shieldnet-backend.service

systemctl daemon-reload
systemctl enable shieldnet-backend
systemctl restart shieldnet-backend

echo "ShieldNet Backend v0.3 installed."
