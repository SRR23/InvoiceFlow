#!/bin/bash
# Start helper for local Compose and Render Docker deploys.
#
# Local Compose: DATABASE_URL is empty → wait for service "db", then migrate (web).
# Render/Neon:   DATABASE_URL is set  → skip Compose host wait, migrate if enabled.
set -euo pipefail

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-0}"
DATABASE_URL="${DATABASE_URL:-}"

if [ -n "${DATABASE_URL}" ]; then
  echo "DATABASE_URL is set — using managed Postgres (e.g. Neon). Skipping Compose db wait."
else
  echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
  until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; do
    sleep 1
  done
  echo "PostgreSQL is ready."
fi

if [ "${RUN_MIGRATIONS}" = "1" ]; then
  echo "Running database migrations..."
  python manage.py migrate --noinput

  # Production image on Render: gather static files into STATIC_ROOT.
  if [ "${DJANGO_SETTINGS_MODULE:-}" = "config.settings.production" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
  fi
fi

exec "$@"
