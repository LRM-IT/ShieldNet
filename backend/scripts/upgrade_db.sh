#!/usr/bin/env bash
set -Eeuo pipefail
cd /opt/shieldnet/backend
sudo -u shieldnet-api /opt/shieldnet/backend/venv/bin/python -m alembic upgrade head
