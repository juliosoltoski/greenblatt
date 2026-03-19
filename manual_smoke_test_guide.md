# Manual Smoke Test Guide

## Purpose

This file is the single place for developer-facing manual verification paths.

Use it after local feature work, before staging deploys, and when updating release notes.

## 1. Bootstrap

```bash
cp .env.example .env
docker compose -f compose.yml -f compose.dev.yml up --build
docker compose -f compose.yml -f compose.dev.yml exec backend python manage.py createsuperuser
```

Check:

- `http://localhost:8080/`
- `http://localhost:8080/login`
- `http://localhost:8080/health/live/`
- `http://localhost:8080/health/ready/`

## 2. Auth And Workspace

1. Sign in at `http://localhost:8080/login`.
2. Open `http://localhost:8080/app`.
3. Confirm the dashboard loads and shows the authenticated workspace.
4. Open `http://localhost:8000/admin/` and confirm the same account can access Django admin if it is staff.

## 3. Universe Workflow

1. Open `http://localhost:8080/app/universes`.
2. Save one universe using a built-in profile.
3. Save one universe from a manual ticker list.
4. Open one saved universe detail page and confirm the preview list resolves correctly.

## 4. Screen Workflow

1. Open `http://localhost:8080/app/screens`.
2. Launch a screen from a saved universe using default settings first.
3. Wait for the run to finish.
4. Open the screen detail page.
5. Confirm ranked rows, exclusions, and CSV export all work.

## 5. Backtest Workflow

1. Open `http://localhost:8080/app/backtests`.
2. Launch a short-range backtest from a saved universe.
3. Wait for the run to finish.
4. Open the detail page.
5. Confirm the equity curve, trades, review targets, final holdings, and ZIP export.

## 6. Templates And History

1. Open `http://localhost:8080/app/history`.
2. Save one prior screen or backtest as a template.
3. Open `http://localhost:8080/app/templates`.
4. Launch from the template and also open it as a draft.
5. Compare two runs of the same type in history.

## 7. Jobs, Schedules, And Alerts

1. Open `http://localhost:8080/app/jobs` and run the smoke job.
2. Confirm timeline events stream in without a manual page refresh.
3. Request cancellation for a running job, then launch another smoke job and confirm retry works after it finishes.
4. Open `http://localhost:8080/app/schedules` and create a recurring schedule from a template.
5. Set a review status on the schedule and use `Run now` to trigger it immediately.
6. Open `http://localhost:8080/app/alerts`, set workspace and personal notification preferences, create an alert rule, and launch a matching run.
7. Confirm a notification event is recorded with the expected channel and destination.

## 8. Collaboration And Sharing

1. Open `http://localhost:8080/app/collaboration`.
2. Create a collection and confirm it appears in the activity feed.
3. Open a template or run detail page and add a comment.
4. Create a read-only share link and open the generated `/shared/<token>` URL in a separate browser session.
5. Confirm the shared page is read-only and shows the expected resource payload.

## 9. Provider And Ops Checks

Provider diagnostics:

- `GET /api/v1/providers/`
- `GET /api/v1/providers/?probe=true`

Artifact cleanup dry run:

```bash
docker compose -f compose.yml -f compose.dev.yml exec backend \
  python manage.py cleanup_artifacts --dry-run
```

Metrics check:

- `GET /metrics/`
- if `METRICS_AUTH_TOKEN` is set, send either `Authorization: Bearer <token>` or `X-Metrics-Token: <token>`

## 10. Staging-Oriented Checks

Validate the rendered config before any staging push:

```bash
docker compose -f compose.yml config
docker compose --env-file .env.staging.example -f compose.yml -f infra/compose.staging.yml config
```

If a feature changes deploy, backup, or rollback behavior, also review:

- [`infra/operations.md`](/home/jsoltoski/greenblatt/infra/operations.md)
- [`infra/scripts/`](/home/jsoltoski/greenblatt/infra/scripts)

## 11. After Verification

- Update [release_notes.md](/home/jsoltoski/greenblatt/release_notes.md) with user-visible changes, migration notes, and smoke-test coverage.
- Update [README.md](/home/jsoltoski/greenblatt/README.md) only if the user-facing setup or entry-point docs changed.
