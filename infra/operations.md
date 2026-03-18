# Operations Guide

This document covers the staging and production-facing workflow introduced in milestone `M9`.

## 1. Environment Files

Use these examples as the starting point:

- `.env.example` for local development
- `.env.staging.example` for staging and production-like deployment

At minimum, staging should define:

- immutable `BACKEND_IMAGE` and `FRONTEND_IMAGE` tags
- a non-dev `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`
- secure-cookie and HSTS settings
- SMTP credentials for notification delivery
- `METRICS_AUTH_TOKEN` for the `/metrics/` endpoint
- Sentry values if remote error reporting is enabled

## 2. Compose Files

- `compose.yml`: base stack used for both local and deployed environments
- `compose.dev.yml`: bind-mount and live-reload overrides for local development
- `infra/compose.staging.yml`: staging hardening overrides, restart policies, internal-only data-service ports, and pull-first image behavior

Staging commands should use:

```bash
docker compose --env-file .env.staging -f compose.yml -f infra/compose.staging.yml ...
```

## 3. CI/CD

Two workflows now exist:

- `.github/workflows/ci.yml`
  - core tests
  - backend tests
  - frontend build
  - Docker image build
  - `python manage.py check --deploy --fail-level WARNING`
- `.github/workflows/release-staging.yml`
  - builds and pushes backend/frontend images to GHCR
  - tags each release with `${GITHUB_SHA}`
  - updates the mutable `:staging` tags
  - optionally SSHes into the staging host and runs `infra/scripts/deploy_staging.sh`

The staging workflow expects these GitHub secrets:

- `STAGING_SSH_HOST`
- `STAGING_SSH_USER`
- `STAGING_SSH_KEY`
- `STAGING_APP_PATH`
- optional `STAGING_SSH_PORT`
- optional `STAGING_ENV_FILE_PATH`

## 4. Staging Deployment

Prepare the host once:

1. Clone the repo to the target host.
2. Copy `.env.staging.example` to `.env.staging` and replace every placeholder secret.
3. Ensure Docker and Docker Compose are installed on the host.
4. Ensure the host can pull the referenced GHCR images.

Deploy a release:

```bash
cp .env.staging.example .env.staging
BACKEND_IMAGE=ghcr.io/<owner>/greenblatt-backend:<sha> \
FRONTEND_IMAGE=ghcr.io/<owner>/greenblatt-frontend:<sha> \
ENV_FILE=.env.staging \
./infra/scripts/deploy_staging.sh
```

The deploy script:

- optionally backs up Postgres and artifact storage first
- pulls the requested images
- runs `migrate`
- runs `collectstatic`
- starts backend, worker, beat, frontend, and proxy
- runs `check --deploy`
- runs smoke checks against the live proxy URL

## 5. Smoke Tests

`infra/scripts/smoke_test.sh` verifies:

- frontend root page responds
- `/health/live/` returns `ok`
- `/api/health/` returns `ok`
- `/metrics/` responds when `METRICS_AUTH_TOKEN` is configured
- optional auth smoke if `SMOKE_USERNAME` and `SMOKE_PASSWORD` are set

Example:

```bash
ENV_FILE=.env.staging APP_BASE_URL=https://staging.example.com ./infra/scripts/smoke_test.sh
```

## 6. Backup and Restore

Backup commands:

```bash
ENV_FILE=.env.staging ./infra/scripts/backup_postgres.sh
ENV_FILE=.env.staging ./infra/scripts/backup_artifacts.sh
```

Restore commands are destructive and require `FORCE=true`:

```bash
FORCE=true ENV_FILE=.env.staging ./infra/scripts/restore_postgres.sh backups/postgres-<timestamp>.sql.gz
FORCE=true ENV_FILE=.env.staging ./infra/scripts/restore_artifacts.sh backups/artifacts-<timestamp>.tar.gz
```

Artifact backup behavior:

- `filesystem`: archive the backend artifact root
- any non-filesystem storage backend in this Compose stack: archive MinIO’s `/data` volume

Recommended operating discipline:

- take a Postgres backup before each deploy
- take an artifact backup before each deploy that changes result persistence
- keep at least one verified restore point from a known-good release
- rehearse restore on staging periodically

## 7. Rollback

Rollback uses prior immutable image tags:

```bash
ROLLBACK_BACKEND_IMAGE=ghcr.io/<owner>/greenblatt-backend:<previous-sha> \
ROLLBACK_FRONTEND_IMAGE=ghcr.io/<owner>/greenblatt-frontend:<previous-sha> \
ENV_FILE=.env.staging \
./infra/scripts/rollback_staging.sh
```

Rollback steps:

1. select the last known-good backend and frontend image tags
2. run the rollback script
3. rerun smoke tests
4. inspect logs, `/metrics/`, and Sentry before reopening traffic

## 8. Observability

The backend now provides:

- structured logs with `request_id`, `correlation_id`, `job_id`, `task_id`, `workspace_id`, and `user_id`
- Sentry initialization for Django and Celery when `SENTRY_DSN` is set
- `/metrics/` with Prometheus-format counters and database-backed gauges

Available metrics include:

- HTTP request counts and latency
- API throttle rejections
- workspace concurrency rejections
- persisted job counts by type and state
- queue latency and run duration
- provider failure counts
- notification event counts

Protect `/metrics/` by setting `METRICS_AUTH_TOKEN` and passing it as:

- `Authorization: Bearer <token>`
- or `X-Metrics-Token: <token>`

## 9. Load Testing

Use a realistic saved template rather than synthetic no-op jobs:

```bash
docker compose -f compose.yml -f compose.dev.yml exec backend \
  python manage.py loadtest_runs --template-id 1 --launch-count 5 --wait --poll-interval 5
```

Recommended practice:

- use a template backed by a representative universe size
- run screens and backtests separately so queue pressure is easy to attribute
- compare queue latency and run duration before and after provider/config changes
- inspect worker logs, `/metrics/`, and Postgres utilization during the run
