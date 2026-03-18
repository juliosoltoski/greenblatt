#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_env_file
require_force_flag

archive_path="${1:-}"
if [[ -z "$archive_path" || ! -f "$archive_path" ]]; then
  echo "Usage: FORCE=true $0 /path/to/artifacts-backup.tar.gz" >&2
  exit 1
fi

storage_backend="${ARTIFACT_STORAGE_BACKEND:-filesystem}"

if [[ "$storage_backend" == "filesystem" ]]; then
  gunzip -c "$archive_path" | docker_compose exec -T backend \
    sh -c "rm -rf \"${ARTIFACT_STORAGE_ROOT:-/var/lib/greenblatt/artifacts}\"/* && mkdir -p \"${ARTIFACT_STORAGE_ROOT:-/var/lib/greenblatt/artifacts}\" && tar -xf - -C \"${ARTIFACT_STORAGE_ROOT:-/var/lib/greenblatt/artifacts}\""
else
  gunzip -c "$archive_path" | docker_compose exec -T minio \
    sh -c "rm -rf /data/* && mkdir -p /data && tar -xf - -C /data"
fi

echo "Artifact restore completed from $archive_path"
