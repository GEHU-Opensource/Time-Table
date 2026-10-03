#!/bin/sh
set -eu

role="${1:-web}"
if [ "$#" -gt 0 ]; then
  shift
fi

if [ "$role" = "migrate" ]; then
  : "${DATABASE_URL_OWNER:?DATABASE_URL_OWNER is required for the migrate role}"
  export DATABASE_URL="$DATABASE_URL_OWNER"
fi

: "${DATABASE_URL:?DATABASE_URL is required}"

wait_for_database() {
  attempts=0
  until python - <<'PY'
import os
import sys

import psycopg

try:
    psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3).close()
except Exception as error:
    print(f"database not ready: {error}", file=sys.stderr)
    sys.exit(1)
PY
  do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "database did not become ready after ${attempts} attempts" >&2
      exit 1
    fi
    sleep 2
  done
}

wait_for_database

case "$role" in
  migrate)
    python manage.py migrate --noinput
    exit 0
    ;;
  web)
    python manage.py check --deploy --fail-level WARNING
    exec "$@"
    ;;
  worker)
    python manage.py check --fail-level WARNING
    exec "$@"
    ;;
  *)
    echo "unknown role: $role (expected web, worker or migrate)" >&2
    exit 64
    ;;
esac
