#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:?APP_DIR is required}"
SERVICE_NAME="${SERVICE_NAME:-ttcdata.service}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"

cd "$APP_DIR"

git fetch --prune origin
git checkout "$DEPLOY_BRANCH"
git pull --ff-only origin "$DEPLOY_BRANCH"

python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/pip install -r requirements.txt

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

if command -v psql >/dev/null 2>&1; then
  if [ -n "${DB_HOST:-}" ] && [ -n "${DB_PORT:-}" ] && [ -n "${DB_USER:-}" ] && [ -n "${DB_PASSWORD:-}" ] && [ -n "${DB_NAME:-}" ]; then
    PGPASSWORD="$DB_PASSWORD" psql \
      -h "$DB_HOST" \
      -p "$DB_PORT" \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      -f sql/001_album_cleaning_tables.sql
  else
    echo "Skipping SQL migration: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, or DB_NAME is missing."
  fi
else
  echo "Skipping SQL migration: psql is not installed on the deployment server."
fi

if command -v systemctl >/dev/null 2>&1; then
  if sudo -n true 2>/dev/null; then
    sudo -n systemctl restart "$SERVICE_NAME"
    sudo -n systemctl status "$SERVICE_NAME" --no-pager --lines=20
  else
    cat << EOF
Deployment updated the code and database, but could not restart $SERVICE_NAME.

The deploy user needs passwordless sudo for systemctl. On the VM, run:

  sudo visudo

Then add a line like this, replacing the username and systemctl path if needed:

  $(whoami) ALL=(ALL) NOPASSWD: /bin/systemctl restart $SERVICE_NAME, /bin/systemctl status $SERVICE_NAME

After saving, rerun the GitHub Actions deployment.
EOF
    exit 1
  fi
else
  echo "systemctl is unavailable. Restart the app process manually."
fi
