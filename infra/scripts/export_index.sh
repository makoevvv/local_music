#!/usr/bin/env bash
# Daily/weekly library index export. See docs/09-infrastructure.md and docs/16-library-index-and-restore.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE=(docker compose -p local_music -f "${ROOT}/infra/docker-compose.yml")
DATE="$(date +%F)"
WEEKDAY="$(date +%u)" # 1=Monday … 7=Sunday
EXPORT_DIR="${ROOT}/data/exports"
mkdir -p "${EXPORT_DIR}"

# Daily minimal export
"${COMPOSE[@]}" exec -T backend python -m app.cli index export --minimal \
  --out "/data/exports/library-${DATE}.jsonl.gz"

# Weekly full export (Sunday)
if [[ "${WEEKDAY}" == "7" ]]; then
  "${COMPOSE[@]}" exec -T backend python -m app.cli index export --include-covers \
    --out "/data/exports/library-full-${DATE}.tar.gz"
fi

# Keep last 14 daily + 8 weekly dumps
find "${EXPORT_DIR}" -maxdepth 1 -name 'library-*.jsonl.gz' -mtime +14 -delete || true
find "${EXPORT_DIR}" -maxdepth 1 -name 'library-full-*.tar.gz' -mtime +56 -delete || true
