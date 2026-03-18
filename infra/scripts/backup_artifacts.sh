#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_env_file
ensure_backup_dir

archive_path="${1:-$BACKUP_DIR/artifacts-$(timestamp_utc).tar.gz}"
storage_backend="${ARTIFACT_STORAGE_BACKEND:-filesystem}"

if [[ "$storage_backend" == "filesystem" ]]; then
  docker_compose exec -T backend \
    tar -C "${ARTIFACT_STORAGE_ROOT:-/var/lib/greenblatt/artifacts}" -czf - . > "$archive_path"
else
  docker_compose exec -T minio tar -C /data -czf - . > "$archive_path"
fi

echo "Artifact backup written to $archive_path"
