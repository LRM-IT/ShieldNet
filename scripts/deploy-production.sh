#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR=${PROJECT_DIR:-/opt/shieldnet}
BACKEND_SERVICE=${BACKEND_SERVICE:-shieldnet-backend}
BOT_SERVICE=${BOT_SERVICE:-shieldnet-bot}
SCHEDULER_SERVICE=${SCHEDULER_SERVICE:-shieldnet-scheduler}
BACKEND_VENV=${BACKEND_VENV:-/var/lib/shieldnet/venvs/backend}
DEPLOY_BROWSER=${DEPLOY_BROWSER:-/var/www/shieldnet-admin/browser}
DOMAIN=${DOMAIN:-shieldnet.discord.lrm-it.com}
BACKUP_ROOT=${BACKUP_ROOT:-/opt/shieldnet-backups}
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/deploy-$STAMP"
BUILD_BROWSER="$PROJECT_DIR/admin-frontend/dist/shieldnet-admin/browser"

log() { printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || fail "Run as root"
[[ -d "$PROJECT_DIR/.git" ]] || fail "$PROJECT_DIR is not a Git repository"
[[ -x "$BACKEND_VENV/bin/python" ]] || fail "Backend Python not found: $BACKEND_VENV/bin/python"

for cmd in git rsync npm curl systemctl nginx sudo; do
    command -v "$cmd" >/dev/null 2>&1 || fail "Missing command: $cmd"
done

BACKEND_USER=$(systemctl show -p User --value "$BACKEND_SERVICE")
BACKEND_GROUP=$(systemctl show -p Group --value "$BACKEND_SERVICE")
[[ -n "$BACKEND_USER" ]] || BACKEND_USER=root
[[ -n "$BACKEND_GROUP" ]] || BACKEND_GROUP="$BACKEND_USER"

rollback() {
    local exit_code=$?
    trap - ERR
    echo
    echo "Deployment failed. Restoring backup: $BACKUP_DIR"

    if [[ -d "$BACKUP_DIR/source" ]]; then
        rsync -a --delete \
            --exclude='.git/' \
            --exclude='.env' \
            --exclude='.env.*' \
            --exclude='node_modules/' \
            --exclude='dist/' \
            --exclude='venv/' \
            --exclude='.venv/' \
            --exclude='__pycache__/' \
            --exclude='*.pyc' \
            --exclude='*.pyo' \
            "$BACKUP_DIR/source/" "$PROJECT_DIR/" || true
    fi

    if [[ -d "$BACKUP_DIR/browser" ]]; then
        mkdir -p "$DEPLOY_BROWSER"
        rsync -a --delete "$BACKUP_DIR/browser/" "$DEPLOY_BROWSER/" || true
    fi

    restorecon -RF "$PROJECT_DIR" "$DEPLOY_BROWSER" 2>/dev/null || true
    systemctl restart "$BACKEND_SERVICE" 2>/dev/null || true
    exit "$exit_code"
}
trap rollback ERR

log "Checking repository state"
cd "$PROJECT_DIR"
[[ -z "$(git status --porcelain)" ]] || fail "Repository has uncommitted changes"

CURRENT_BRANCH=$(git branch --show-current)
CURRENT_COMMIT=$(git rev-parse HEAD)
printf 'Branch: %s\nCommit: %s\n' "$CURRENT_BRANCH" "$CURRENT_COMMIT"

log "Creating backup"
mkdir -p "$BACKUP_DIR/source" "$BACKUP_DIR/browser"
rsync -a \
    --exclude='.git/' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='node_modules/' \
    --exclude='dist/' \
    --exclude='venv/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.pytest_cache/' \
    --exclude='.mypy_cache/' \
    --exclude='.ruff_cache/' \
    "$PROJECT_DIR/" "$BACKUP_DIR/source/"

if [[ -d "$DEPLOY_BROWSER" ]]; then
    rsync -a "$DEPLOY_BROWSER/" "$BACKUP_DIR/browser/"
fi

log "Removing generated Python caches"
find "$PROJECT_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_DIR" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true

log "Validating backend source"
sudo -u "$BACKEND_USER" test -r "$PROJECT_DIR/backend/app/main.py"
sudo -u "$BACKEND_USER" bash -lc "cd '$PROJECT_DIR/backend' && '$BACKEND_VENV/bin/python' -m compileall -q app && '$BACKEND_VENV/bin/python' -c 'import app.main'"

if [[ -x "$BACKEND_VENV/bin/alembic" ]]; then
    log "Applying database migrations"
    sudo -u "$BACKEND_USER" bash -lc "cd '$PROJECT_DIR/backend' && '$BACKEND_VENV/bin/alembic' upgrade head"
fi

log "Building Angular frontend"
cd "$PROJECT_DIR/admin-frontend"
npm ci --no-audit --no-fund
npm run build -- --configuration production
[[ -f "$BUILD_BROWSER/index.html" ]] || fail "Angular build output not found: $BUILD_BROWSER/index.html"

log "Publishing frontend"
mkdir -p "$DEPLOY_BROWSER"
rsync -a --delete "$BUILD_BROWSER/" "$DEPLOY_BROWSER/"
restorecon -RF "$PROJECT_DIR" "$DEPLOY_BROWSER" 2>/dev/null || true

log "Checking Nginx configuration"
nginx -t

log "Restarting backend"
systemctl restart "$BACKEND_SERVICE"

log "Waiting for backend readiness"
READY=0
for _ in $(seq 1 40); do
    code=$(curl -sS -o /tmp/shieldnet-backend-ready.out -w '%{http_code}' --max-time 3 \
        http://127.0.0.1:8000/api/v1/auth/me || true)
    if [[ "$code" =~ ^(200|401|403)$ ]]; then
        READY=1
        break
    fi
    sleep 2
done

if [[ "$READY" != 1 ]]; then
    systemctl status "$BACKEND_SERVICE" --no-pager || true
    journalctl -u "$BACKEND_SERVICE" -n 120 --no-pager || true
    fail "Backend did not become ready within 80 seconds"
fi

for service in "$BOT_SERVICE" "$SCHEDULER_SERVICE"; do
    if systemctl list-unit-files "${service}.service" --no-legend 2>/dev/null | grep -q "${service}.service"; then
        log "Restarting $service"
        systemctl restart "$service"
    fi
done

log "Reloading Nginx"
systemctl reload nginx

log "Checking public site"
PUBLIC_READY=0
for _ in $(seq 1 15); do
    code=$(curl -ksS -o /dev/null -w '%{http_code}' --max-time 5 "https://$DOMAIN/" || true)
    if [[ "$code" =~ ^(200|301|302)$ ]]; then
        PUBLIC_READY=1
        break
    fi
    sleep 2
done
[[ "$PUBLIC_READY" == 1 ]] || fail "Public site check failed"

trap - ERR
log "Deployment completed"
echo "Commit: $CURRENT_COMMIT"
echo "Backup: $BACKUP_DIR"
echo "Site: https://$DOMAIN/"
