#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

require_env_file

app_base_url="${APP_BASE_URL:-http://127.0.0.1:${PROXY_PORT:-80}}"
cookie_jar="$(mktemp)"
trap 'rm -f "$cookie_jar"' EXIT

curl -fsS "$app_base_url/" > /dev/null
curl -fsS "$app_base_url/health/live/" | grep -q '"status": "ok"'
curl -fsS "$app_base_url/api/health/" | grep -q '"status": "ok"'

if [[ -n "${METRICS_AUTH_TOKEN:-}" ]]; then
  curl -fsS -H "Authorization: Bearer ${METRICS_AUTH_TOKEN}" "$app_base_url/metrics/" | grep -q "greenblatt_"
fi

if [[ -n "${SMOKE_USERNAME:-}" && -n "${SMOKE_PASSWORD:-}" ]]; then
  csrf_json="$(curl -fsS -c "$cookie_jar" "$app_base_url/api/v1/auth/csrf/")"
  echo "$csrf_json" | grep -q '"detail": "CSRF cookie set."'
  csrf_token="$(awk '$6 == "csrftoken" {print $7}' "$cookie_jar" | tail -n 1)"
  curl -fsS \
    -b "$cookie_jar" \
    -c "$cookie_jar" \
    -H "Content-Type: application/json" \
    -H "X-CSRFToken: $csrf_token" \
    -d "{\"username\":\"${SMOKE_USERNAME}\",\"password\":\"${SMOKE_PASSWORD}\"}" \
    "$app_base_url/api/v1/auth/login/" | grep -q "\"username\": \"${SMOKE_USERNAME}\""
  curl -fsS -b "$cookie_jar" "$app_base_url/api/v1/auth/me/" | grep -q "\"username\": \"${SMOKE_USERNAME}\""
fi

echo "Smoke tests passed against $app_base_url"
