#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_env_file

if [[ "${BACKUP_BEFORE_DEPLOY:-true}" == "true" ]]; then
  "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backup_postgres.sh"
  "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backup_artifacts.sh"
fi

docker_compose pull backend worker beat frontend proxy
docker_compose up -d postgres redis minio
docker_compose run --rm backend python manage.py migrate --noinput
docker_compose run --rm backend python manage.py collectstatic --noinput
docker_compose up -d backend worker beat frontend proxy
docker_compose exec -T backend python manage.py check --deploy --fail-level WARNING
"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smoke_test.sh"

echo "Staging deployment completed."
