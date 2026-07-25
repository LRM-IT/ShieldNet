#!/usr/bin/env bash
set -Eeuo pipefail

echo "== Service =="
systemctl is-active shieldnet-backend

echo "== Database migration =="
cd /opt/shieldnet/backend
sudo -u shieldnet-api /opt/shieldnet/backend/venv/bin/python -m alembic current

echo "== Health =="
curl -fsS http://127.0.0.1:8000/api/v1/health
echo
curl -fsS http://127.0.0.1:8000/api/v1/health/database
echo

echo "== Core tables =="
sudo -u postgres psql -d shieldnet -c "\dt core.*"
