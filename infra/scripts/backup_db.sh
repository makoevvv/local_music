#!/usr/bin/env bash
# Daily Postgres dump. See docs/09-infrastructure.md.
# Keeps at least 7 days of db_YYYY-MM-DD.sql.gz (older files are removed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE=(docker compose -p local_music -f "${ROOT}/infra/docker-compose.yml")
DATE="$(date +%F)"
BACKUP_DIR="${BACKUP_DIR:-${ROOT}/backups}"

if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_DB:-}" ]]; then
  env_file="${ROOT}/.env"
  if [[ -f "${env_file}" ]]; then
    while IFS= read -r line || [[ -n "${line}" ]]; do
      case "${line}" in
        POSTGRES_USER=*|POSTGRES_DB=*)
          key="${line%%=*}"
          value="${line#*=}"
          if [[ -z "${!key:-}" ]]; then
            printf -v "${key}" '%s' "${value}"
            export "${key?}"
          fi
          ;;
      esac
    done < "${env_file}"
  fi
fi

POSTGRES_USER="${POSTGRES_USER:-music}"
POSTGRES_DB="${POSTGRES_DB:-local_music}"

mkdir -p "${BACKUP_DIR}"
outfile="${BACKUP_DIR}/db_${DATE}.sql.gz"
partial="${outfile}.partial"
rm -f "${partial}"

"${COMPOSE[@]}" exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
  | gzip > "${partial}"
mv "${partial}" "${outfile}"

find "${BACKUP_DIR}" -maxdepth 1 -name 'db_*.sql.gz' -mtime +7 -delete
