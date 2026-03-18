#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_env_file
ensure_backup_dir

archive_path="${1:-$BACKUP_DIR/postgres-$(timestamp_utc).sql.gz}"

docker_compose exec -T postgres \
  pg_dump \
  -U "${POSTGRES_USER:-greenblatt}" \
  -d "${POSTGRES_DB:-greenblatt}" \
  | gzip -c > "$archive_path"

echo "Postgres backup written to $archive_path"
