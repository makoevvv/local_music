#!/usr/bin/env bash
# Daily library maintenance for stage 4.1: expire uploads, retry albums, match public sources.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE=(docker compose -p local_music -f "${ROOT}/infra/docker-compose.yml")

"${COMPOSE[@]}" exec -T backend python -m app.cli cleanup-uploads
"${COMPOSE[@]}" exec -T backend python -m app.cli reconcile-albums --limit 50
"${COMPOSE[@]}" exec -T backend python -m app.cli match-user-uploads --limit 5
