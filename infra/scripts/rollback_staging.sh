#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_env_file

if [[ -z "${ROLLBACK_BACKEND_IMAGE:-}" || -z "${ROLLBACK_FRONTEND_IMAGE:-}" ]]; then
  echo "Set ROLLBACK_BACKEND_IMAGE and ROLLBACK_FRONTEND_IMAGE before running rollback." >&2
  exit 1
fi

export BACKEND_IMAGE="$ROLLBACK_BACKEND_IMAGE"
export FRONTEND_IMAGE="$ROLLBACK_FRONTEND_IMAGE"

docker_compose pull backend worker beat frontend
docker_compose up -d backend worker beat frontend proxy
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smoke_test.sh"

echo "Rollback completed using backend=$BACKEND_IMAGE frontend=$FRONTEND_IMAGE"
