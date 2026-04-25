#!/usr/bin/env bash
# Nightly PostgreSQL logical backup (pg_dump). Run via cron or CI.
# Usage: DATABASE_URL=postgresql://... ./backup_postgres.sh [output_dir]
set -euo pipefail
OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${OUT_DIR}/biomarker_${STAMP}.sql.gz"
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi
pg_dump "$DATABASE_URL" | gzip > "$OUT_FILE"
echo "Wrote ${OUT_FILE}"
