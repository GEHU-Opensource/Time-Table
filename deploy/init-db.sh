#!/bin/bash
set -euo pipefail

: "${OWNER_DB_PASSWORD:?OWNER_DB_PASSWORD is required}"
: "${WEB_DB_PASSWORD:?WEB_DB_PASSWORD is required}"
: "${WORKER_DB_PASSWORD:?WORKER_DB_PASSWORD is required}"
: "${OPS_DB_PASSWORD:?OPS_DB_PASSWORD is required}"

for secret in "$OWNER_DB_PASSWORD" "$WEB_DB_PASSWORD" "$WORKER_DB_PASSWORD" "$OPS_DB_PASSWORD"; do
  case "$secret" in
    *[!A-Za-z0-9_-]*)
      echo "database passwords must contain only A-Z a-z 0-9 _ - (use: openssl rand -hex 32)" >&2
      exit 1
      ;;
  esac
done

rendered="$(mktemp)"
trap 'rm -f "$rendered"' EXIT

sed \
  -e "s|CHANGE_ME_OWNER|${OWNER_DB_PASSWORD}|" \
  -e "s|CHANGE_ME_WEB|${WEB_DB_PASSWORD}|" \
  -e "s|CHANGE_ME_WORKER|${WORKER_DB_PASSWORD}|" \
  -e "s|CHANGE_ME_OPS|${OPS_DB_PASSWORD}|" \
  /docker-entrypoint-initdb.d/roles.sql > "$rendered"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres --file "$rendered"
