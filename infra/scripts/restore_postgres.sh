#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_env_file
require_force_flag

archive_path="${1:-}"
if [[ -z "$archive_path" || ! -f "$archive_path" ]]; then
  echo "Usage: FORCE=true $0 /path/to/postgres-backup.sql.gz" >&2
  exit 1
fi

docker_compose exec -T postgres \
  dropdb --if-exists -U "${POSTGRES_USER:-greenblatt}" "${POSTGRES_DB:-greenblatt}"
docker_compose exec -T postgres \
  createdb -U "${POSTGRES_USER:-greenblatt}" "${POSTGRES_DB:-greenblatt}"
gunzip -c "$archive_path" | docker_compose exec -T postgres \
  psql -U "${POSTGRES_USER:-greenblatt}" -d "${POSTGRES_DB:-greenblatt}"

echo "Postgres restore completed from $archive_path"
