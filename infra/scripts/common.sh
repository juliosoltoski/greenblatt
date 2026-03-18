#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.staging}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

COMPOSE_ARGS=(
  --env-file "$ENV_FILE"
  -f "$ROOT_DIR/compose.yml"
  -f "$ROOT_DIR/infra/compose.staging.yml"
)

docker_compose() {
  docker compose "${COMPOSE_ARGS[@]}" "$@"
}

require_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing env file: $ENV_FILE" >&2
    exit 1
  fi
}

timestamp_utc() {
  date -u +"%Y%m%dT%H%M%SZ"
}

ensure_backup_dir() {
  mkdir -p "$BACKUP_DIR"
}

require_force_flag() {
  if [[ "${FORCE:-false}" != "true" ]]; then
    echo "This operation is destructive. Re-run with FORCE=true." >&2
    exit 1
  fi
}
