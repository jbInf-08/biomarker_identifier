#!/usr/bin/env bash
# Restore from a gzipped pg_dump produced by backup_postgres.sh.
# Usage: DATABASE_URL=postgresql://... ./restore_postgres.sh backup.sql.gz
set -euo pipefail
if [[ -z "${DATABASE_URL:-}" ]] || [[ $# -lt 1 ]]; then
  echo "Usage: DATABASE_URL=postgresql://... $0 backup.sql.gz" >&2
  exit 1
fi
gunzip -c "$1" | psql "$DATABASE_URL"
echo "Restore complete."
