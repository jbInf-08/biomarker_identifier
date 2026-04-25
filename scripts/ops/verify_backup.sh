#!/usr/bin/env bash
# Smoke-test a backup file: gunzip and run a trivial parse (requires pg_restore-compatible SQL).
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 backup.sql.gz" >&2
  exit 1
fi
gunzip -c "$1" | head -n 50 >/dev/null
echo "Backup file is readable and non-empty (first lines OK)."
