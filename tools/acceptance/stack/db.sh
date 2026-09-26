#!/usr/bin/env bash
# A fresh local database for acceptance runs: CI's Supabase shim, every
# migration, the platform seed. Local only — refuses anything but localhost.
#   PGPORT=54329 tools/acceptance/stack/db.sh locah_accept
set -euo pipefail
DB=${1:-locah_accept}
HOST=${PGHOST:-localhost}
PORT=${PGPORT:-54329}
PSQL=${PSQL:-psql}
case "$HOST" in localhost|127.0.0.1) ;; *) echo "local databases only" >&2; exit 1 ;; esac
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
run() { "$PSQL" -h "$HOST" -p "$PORT" -U postgres -q -v ON_ERROR_STOP=1 "$@"; }
run -c "DROP DATABASE IF EXISTS $DB" -c "CREATE DATABASE $DB" -c "ALTER DATABASE $DB SET search_path = public, extensions"
run -d "$DB" -f "$ROOT/infra/deploy/ci-bootstrap.sql"
for f in "$ROOT"/infra/supabase/migrations/*.sql "$ROOT"/infra/supabase/seed/00_platform.sql; do
  run -d "$DB" -f "$f" >/dev/null
done
echo "local database $DB ready"
