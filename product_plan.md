# Product Plan: Greenblatt Web App

## Status Note

This document remains the product and architecture reference for the Greenblatt web app.

The initial delivery roadmap described here has been executed through `M10` in [implementation_plan.md](/home/jsoltoski/greenblatt/implementation_plan.md).
Future polish, deferred scope, and post-M10 roadmap work now live in [nice_to_have_implementation_plan.md](/home/jsoltoski/greenblatt/nice_to_have_implementation_plan.md).

## 1. Objective

Turn the current CLI-based screening and backtesting engine into a deployable web application that supports:

- authenticated users
- reusable saved universes and strategy templates
- async screen and backtest execution
- persistent results, exports, and auditability
- scheduled recurring jobs
- operational visibility and production deployment

The plan should preserve the current investment logic and provider abstraction, not replace it.

## 2. Recommended Product Shape

### Primary user workflows

- Sign in and manage a personal workspace
- Choose a built-in universe or upload/create a custom universe
- Run a screen with configurable filters and momentum mode
- Run a backtest with configurable capital, benchmark, and portfolio size
- Watch progress while long-running jobs execute asynchronously
- Review result tables, equity curves, trades, exclusions, and summary metrics
- Export CSV/JSON artifacts for offline analysis
- Save configurations as reusable templates
- Schedule recurring screens and backtests
- Receive completion notifications and alerts for notable results

### Suggested first release scope

- Single product with authenticated private workspaces
- Manual screen and backtest execution
- Saved universes and saved templates
- Result history and exports
- Job queue, retries, logging, and admin tools

### Explicitly defer from MVP

- Brokerage integration or auto-trading
- Real-time streaming quotes
- Intraday backtesting
- Billing/subscriptions
- Native mobile apps

## 3. Stack Recommendation

### Backend

- Django for the main backend, ORM, auth, admin, migrations, and configuration management
- Django REST Framework for the JSON API, schema generation, serializers, permissions, filtering, pagination, and throttling
- Django Admin for internal operations, job inspection, schedule management, and support workflows
- ASGI deployment for the Django app so the backend is ready for SSE or WebSocket-style progress later if needed

### Async and caching

- Celery for long-running screens, backtests, exports, notifications, and maintenance jobs
- Redis as the Celery broker and Django cache store
- `django-celery-beat` for periodic jobs managed from Django
- Optional `django-celery-results` only if low-level Celery result inspection in Django is valuable; user-facing job status should still live in first-party product tables

### Database and storage

- PostgreSQL as the system of record
- JSONB for flexible run configuration, provider metadata, and artifact manifests
- S3-compatible object storage for large exports and serialized result artifacts
- MinIO in local Docker Compose for development parity

### Frontend

- Next.js with the App Router and TypeScript
- Tailwind CSS for styling
- TanStack Query for API state, polling, and mutations
- TanStack Table for dense tabular screening/backtest data
- Apache ECharts for interactive financial charts and equity curves

### Reverse proxy and deployment

- Caddy as the reverse proxy in Docker deployments for simple TLS and clean routing
- Docker Compose for local development and initial single-host production deployment

## 4. Why This Stack

- Django is the best fit for this product because it provides admin tooling, a mature ORM, built-in auth, and a fast path from internal tool to production app.
- Celery is appropriate because screen and backtest runs can take long enough that they should not execute in request/response paths.
- PostgreSQL is a strong fit because the product needs relational integrity for runs and users, while JSONB is useful for flexible result metadata and evolving provider payloads.
- Next.js is the best frontend choice here because the app will need rich tables, charts, authenticated pages, and a path to public/shareable pages later without replacing the frontend stack.
- Docker Compose is the right starting deployment model because this application can begin as a single-host service and does not require Kubernetes-level operational overhead on day one.

## 5. Product Architecture

### High-level service topology

```text
Browser
  -> Caddy
    -> Next.js frontend
    -> Django API and Django Admin

Django API
  -> PostgreSQL
  -> Redis
  -> Object Storage
  -> Celery broker queue

Celery Worker
  -> current Greenblatt core engine
  -> market data provider(s)
  -> PostgreSQL
  -> Object Storage

Celery Beat
  -> scheduled runs
  -> maintenance jobs
  -> notifications
```

### Routing model

- `/` and authenticated app pages served by Next.js
- `/api/*` served by Django REST API
- `/admin/*` served by Django admin
- optional `/health/*` served by Django for readiness/liveness

### Auth model

- Use Django session-cookie auth for the first version
- Keep frontend and backend on the same parent domain to avoid unnecessary CORS and token complexity
- Use CSRF protection for state-changing requests
- Add OAuth/social login later only if there is clear user demand

## 6. Preserve and Refactor the Existing Codebase

The current project already has a good core split:

- pure ranking logic in `engine.py`
- simulation logic in `simulation.py`
- provider abstraction in `providers/base.py`
- typed configs and result dataclasses in `models.py`
- CLI orchestration in `cli.py`

### Refactor target

- Keep the core domain logic framework-agnostic
- Move web-specific orchestration into Django apps and Celery tasks
- Convert CLI input parsing into reusable service-layer request objects
- Keep the CLI as a thin adapter over the shared service layer so the CLI remains usable for debugging and ops

### Recommended package split

```text
/backend                  Django project
/frontend                 Next.js app
/packages/greenblatt_core Reused engine, provider interfaces, simulation logic
/infra                    Docker, Caddy, deployment scripts
```

If a package split feels too disruptive initially, keep `src/greenblatt` in place and import it from Django until a dedicated `greenblatt_core` package is extracted.

## 7. Backend Application Plan

### Django apps

- `accounts`: users, auth, profile settings
- `workspaces`: personal or team workspaces, memberships, permissions
- `universes`: built-in profiles, custom universes, uploaded ticker lists
- `research`: screen runs, backtest runs, templates, artifacts
- `jobs`: async job tracking, task status, retries, logs
- `schedules`: recurring jobs and schedule definitions
- `notifications`: email/in-app notifications and alerts
- `providers`: provider configuration, rate limits, health checks, future vendor switching
- `audit`: immutable audit events for important user and system actions

### Service layer

Create backend services that wrap the current core package:

- `UniverseService`
- `ScreenService`
- `BacktestService`
- `ArtifactService`
- `ScheduleService`
- `NotificationService`
- `ProviderHealthService`

These services should be callable from API views, Celery tasks, management commands, and the CLI.

## 8. API Plan

### Core API areas

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/universe-profiles`
- `GET /api/v1/universes`
- `POST /api/v1/universes`
- `GET /api/v1/universes/{id}`
- `POST /api/v1/screens`
- `GET /api/v1/screens`
- `GET /api/v1/screens/{id}`
- `GET /api/v1/screens/{id}/results`
- `GET /api/v1/screens/{id}/export`
- `POST /api/v1/backtests`
- `GET /api/v1/backtests`
- `GET /api/v1/backtests/{id}`
- `GET /api/v1/backtests/{id}/equity-curve`
- `GET /api/v1/backtests/{id}/trades`
- `GET /api/v1/jobs/{id}`
- `POST /api/v1/templates`
- `GET /api/v1/templates`
- `POST /api/v1/schedules`
- `GET /api/v1/schedules`
- `POST /api/v1/alerts`
- `GET /api/v1/alerts`

### API design rules

- Every long-running mutation should return a `job_id`
- Result resources should be queryable separately from job records
- Large tables should be paginated server-side
- Export endpoints should return signed download URLs or artifact IDs
- Version the API from day one
- Generate OpenAPI and derive TypeScript client types for the frontend

## 9. Async Task Plan

### Celery queues

- `default`: lightweight jobs and general async work
- `screening`: current screen runs
- `backtesting`: heavier historical runs
- `maintenance`: cleanup, cache warmups, provider checks
- `notifications`: email and alert dispatch

### Task types

- run screen
- run backtest
- export screen result
- export backtest result
- refresh built-in universe constituents
- warm snapshot cache
- warm price history cache
- evaluate alert rules
- send completion notifications
- cleanup expired artifacts and stale temp files

### Execution flow for a screen run

1. API validates request and creates a `JobRun` plus `ScreenRun`.
2. Celery task resolves the universe and writes normalized job input metadata.
3. Task calls the current screen engine through the service layer.
4. Ranked rows, exclusions, summaries, and export artifacts are persisted.
5. Job status moves to `succeeded`, `failed`, or `partial_failed`.

### Execution flow for a backtest run

1. API validates request and creates a `JobRun` plus `BacktestRun`.
2. Celery task loads tickers, historical prices, and required snapshots.
3. Task executes the backtester and stores summary, trades, review targets, equity curve, and holdings.
4. Export artifacts are generated and attached.
5. Notifications and schedule hooks run after success/failure.

### Operational rules

- Enforce hard task time limits and soft time limits
- Use retry policies with exponential backoff only for transient provider/network failures
- Keep job status in first-party tables so the frontend is not coupled to Celery internals
- Use separate `celery beat` service in production; do not run worker with `-B`
- Add queue concurrency limits because the Yahoo-based provider is rate-limit sensitive
- Add idempotency protection so repeated button clicks do not launch duplicate heavy jobs

### Progress updates

- MVP: frontend polls `GET /api/v1/jobs/{id}` every few seconds
- Later: add SSE for real-time job logs and progress events

## 10. Database Modeling Plan

### Identity and tenancy

#### `user`

- Django auth user

#### `workspace`

- owner
- name
- slug
- plan type
- timezone

#### `workspace_membership`

- workspace
- user
- role: `owner`, `admin`, `analyst`, `viewer`

This is worth adding early even if the app launches as single-user only. It avoids a painful migration if collaboration is added later.

### Securities and universes

#### `security`

- canonical ticker
- normalized ticker
- exchange
- country
- sector
- industry
- latest known company name
- metadata JSONB

#### `universe`

- workspace
- name
- source type: `built_in`, `uploaded_file`, `manual`
- profile key if built-in
- description
- file artifact reference if uploaded

#### `universe_entry`

- universe
- security or raw ticker
- position/order
- inclusion metadata JSONB

### Strategy templates and schedules

#### `strategy_template`

- workspace
- name
- type: `screen`, `backtest`
- configuration JSONB

#### `run_schedule`

- workspace
- template
- cron or interval definition
- enabled flag
- last run at
- next run at
- notification targets JSONB

### Async jobs

#### `job_run`

- workspace
- type
- state: `queued`, `running`, `succeeded`, `failed`, `cancelled`, `partial_failed`
- progress percent
- current step
- error code
- error message
- retry count
- Celery task id
- started at
- finished at
- metadata JSONB

### Screening

#### `screen_run`

- workspace
- job
- requested universe
- resolved universe size
- configuration JSONB
- summary JSONB
- started at
- finished at

#### `screen_result_row`

- screen run
- ticker
- company name
- sector
- industry
- market cap
- ROC
- EY
- enterprise value
- momentum
- ROC rank
- EY rank
- momentum rank
- composite score
- final score

#### `screen_exclusion`

- screen run
- ticker
- reason

### Backtesting

#### `backtest_run`

- workspace
- job
- requested universe
- resolved universe size
- configuration JSONB
- summary JSONB
- started at
- finished at

#### `backtest_equity_point`

- backtest run
- date
- equity
- cash
- position count
- benchmark equity

#### `backtest_trade`

- backtest run
- date
- ticker
- side
- shares
- price
- proceeds
- reason

#### `backtest_review_target`

- backtest run
- date
- target rank
- ticker
- final score
- composite score
- ROC rank
- EY rank
- momentum rank

#### `backtest_final_holding`

- backtest run
- ticker
- shares
- entry date
- entry price
- score

### Artifacts

#### `artifact`

- workspace
- owner type and owner id
- storage backend
- object key
- content type
- file size
- checksum
- artifact type: `csv`, `json`, `parquet`, `upload`
- metadata JSONB

### Alerts and notifications

#### `alert_rule`

- workspace
- type
- target universe/template/run
- condition JSONB
- enabled flag

#### `notification_event`

- workspace
- type
- destination
- payload JSONB
- sent at
- status

### Audit

#### `audit_event`

- workspace
- actor
- event type
- object type
- object id
- payload JSONB
- created at

### Modeling guidance

- Keep relational columns for high-value query fields like ticker, run id, date, and score.
- Use JSONB for flexible config and provider payloads that will evolve.
- Do not store all raw historical price series in PostgreSQL at first.
- Store large exports and serialized artifacts in object storage and keep references in PostgreSQL.
- Add retention rules early so tables like equity points and task logs do not grow without bounds.
- Do not add table partitioning on day one; add it later only if tables such as `backtest_equity_point` prove it necessary in production.

## 11. Market Data and Provider Strategy

### Immediate approach

- Keep the current Yahoo-backed provider for development and early internal use
- Centralize all provider access behind the existing `MarketDataProvider` interface
- Add backend-side rate limiting, retries, and cache warming
- Track provider failures and throttling in provider health records and logs

### Important product risk

Yahoo Finance is acceptable for prototyping and internal tooling, but it is a risk for a deployable product if the app becomes multi-user or commercial.

### Recommended mitigation

- Preserve provider abstraction rigorously
- Design a second provider adapter path for a licensed market data source
- Keep provider-specific payloads out of frontend contracts
- Make run artifacts and normalized results independent from raw provider formats

### Future provider candidates

- Polygon
- Tiingo
- Twelve Data
- Intrinio
- FactSet or Refinitiv for enterprise-grade commercial versions

## 12. Frontend Plan

### Main pages

- login and account pages
- dashboard
- universes list and editor
- new screen form
- screen run detail page
- new backtest form
- backtest run detail page
- templates and schedules
- alerts and notifications
- settings

### Key UI components

- universe picker with built-in profile preview
- ticker upload and validation panel
- run parameter form with presets
- job status banner and progress timeline
- results table with sorting, filtering, pagination, and CSV export
- exclusions table
- equity curve chart
- drawdown chart
- trade ledger table
- run comparison view
- empty, loading, error, and partial-failure states

### Frontend data strategy

- Use server rendering only where it adds clear value
- For authenticated app pages, rely mostly on client-side data fetching with TanStack Query
- Poll job status endpoints while async runs are active
- Cache read-heavy endpoints conservatively because user actions can invalidate data often
- Generate API types from OpenAPI to avoid frontend/backend drift

### UX features worth adding early

- duplicate a prior run
- save a run as template
- compare two screen runs
- compare a backtest against benchmark and prior runs
- share a read-only result link inside a workspace
- bookmark favorite tickers and universes

## 13. Docker and Compose Plan

### Images

- `backend`: Django API and admin
- `worker`: Celery worker image built from the backend image
- `beat`: Celery beat image built from the backend image
- `frontend`: Next.js app
- `proxy`: Caddy

### Compose services

- `proxy`
- `frontend`
- `backend`
- `worker`
- `beat`
- `postgres`
- `redis`
- `minio` as a dev/default object storage option
- `flower` as an optional profile for queue debugging

### Named volumes

- `postgres_data`
- `redis_data`
- `minio_data`
- optional `backend_static`

### Environment files

- `.env` for shared non-secret values
- `.env.local` or host-managed secret injection for secrets
- distinct settings for `dev`, `staging`, and `prod`

### Compose file strategy

- `compose.yml` for the baseline stack
- `compose.dev.yml` for bind mounts, live reload, debug tools, and Flower
- `compose.prod.yml` for hardened runtime config, pinned images, and disabled dev mounts

### Container runtime guidance

- One process per container
- Health checks for frontend, backend, postgres, redis, and minio
- `docker compose config` should be part of deployment validation
- Use explicit restart policies
- Run database migrations as a release step before promoting traffic

### Static and media strategy

- Django admin static served via WhiteNoise or collected to a mounted static directory
- Next.js static assets served by the Next.js container and proxied by Caddy
- Uploaded universe files and exported artifacts stored in object storage, not in ephemeral container filesystems

## 14. Environment Plan

### Local development

- full stack via Docker Compose
- seeded admin user
- MinIO enabled
- Flower enabled
- hot reload for Django and Next.js

### Staging

- same topology as production
- real Postgres and Redis persistence
- lower queue concurrency and smaller scheduled workloads
- synthetic smoke jobs and alert testing

### Production

- single-host Docker Compose deployment initially
- Caddy-managed TLS
- Postgres backups and restore drills
- object storage versioning for artifacts if available
- Sentry or similar error monitoring

### Scale-up path

Move beyond Compose when any of these become true:

- need multi-host failover
- queue depth consistently exceeds single-host worker capacity
- high-availability database requirements exceed the simple deployment model
- deployment frequency and rollback needs justify orchestrator tooling

## 15. CI/CD and Release Management

### Pipeline stages

- lint and unit tests for the core package, backend, and frontend
- backend API tests and Celery integration tests
- frontend build and end-to-end smoke tests
- Docker image builds for `backend`, `worker`, `beat`, `frontend`, and `proxy`
- dependency and image vulnerability scanning
- push immutable image tags for staging and production

### Release flow

- merge to main triggers staging image builds and deployment
- run migrations before switching traffic
- run smoke checks against `/health/*`, login, and one lightweight job workflow
- promote the exact same image tags to production after staging passes

### Rollback strategy

- keep the previous production image tags available
- use backwards-compatible migrations whenever possible
- treat destructive schema changes as multi-step releases
- document a rollback path for migrations that cannot be reversed automatically

## 16. Security and Reliability Plan

### Backend hardening

- run `manage.py check --deploy` before releases
- `DEBUG = False` in production
- explicit `ALLOWED_HOSTS`
- secure session and CSRF cookies
- HTTPS everywhere
- secret injection from environment or secret files

### Access control

- workspace-level permissions
- Django admin restricted to staff users
- object-level permissions on universes, runs, templates, and schedules

### Rate limiting and abuse prevention

- API throttling for job creation
- per-workspace concurrency limits
- provider-side request throttling and locking
- upload size limits and file validation for ticker files

### Reliability

- retries only for transient failures
- task timeouts and dead-letter visibility through logs and admin
- backups for Postgres and object storage
- resumable or restartable export generation
- structured logs with correlation ids linking request, job, and artifact events

## 17. Observability and Admin Operations

### Must-have observability

- structured JSON logs
- request ids and job ids in every log line
- error monitoring with Sentry
- metrics for job counts, queue depth, task duration, provider failures, and run latency

### Internal admin capabilities

- browse users, workspaces, universes, schedules, runs, and artifacts in Django admin
- disable broken schedules quickly
- retry failed jobs
- inspect provider throttling trends
- re-run a job from prior configuration

### Optional ops additions

- Flower for Celery queue debugging
- Prometheus and Grafana for metrics dashboards
- uptime monitoring for public endpoints

## 18. Testing Strategy

### Core

- keep and expand the current engine/backtester unit tests
- add provider contract tests
- add regression fixtures for screen and backtest outputs

### Backend

- model tests
- service-layer tests
- API tests
- Celery task integration tests
- migration tests for critical schema changes

### Frontend

- component tests
- API contract tests against generated types
- Playwright end-to-end flows for login, run launch, polling, and result review

### Deployment

- image build tests
- compose smoke tests
- health check verification
- backup/restore drill in staging

## 19. Delivery Roadmap

### Phase 0: Core extraction and architectural prep

- isolate the current reusable core package
- define service-layer contracts for screen and backtest execution
- document provider abstraction and output schemas

### Phase 1: Infrastructure and backend scaffold

- create Django project, DRF base API, settings split, auth, admin, Postgres integration
- add Dockerfiles, Compose stack, Caddy, Redis, Celery, and MinIO
- establish CI for tests and image builds

### Phase 2: Workspaces, universes, templates

- implement users, workspace model, permissions
- implement built-in and custom universes
- add file upload and validation for ticker lists
- add template CRUD

### Phase 3: Screening workflow

- implement `ScreenRun`, result persistence, exports, and polling
- wire Celery tasks to the current screen engine
- build frontend pages for launching and reviewing screens

### Phase 4: Backtesting workflow

- implement `BacktestRun`, equity curve persistence, trades, holdings, and exports
- wire Celery tasks to the current backtester
- build frontend pages for launching and reviewing backtests

### Phase 5: Scheduling, notifications, and alerts

- add Celery beat, recurring schedules, notification destinations, and alert rules
- add completion emails and recurring digest/alert workflows

### Phase 6: Hardening and product polish

- observability, retry policy tuning, backup automation, admin workflows
- result comparison views
- permission hardening
- staging soak testing

### Phase 7: Provider upgrade path

- add at least one second provider adapter
- support provider selection by environment or workspace
- validate that frontend contracts do not change when provider changes

## 20. Suggested Nice Additions Beyond the Request

- read-only share links for finished runs
- watchlists and saved favorite tickers
- benchmark library management
- diff view between two runs to show rank changes
- email or Slack notifications on completed jobs
- provider health dashboard and failure budget tracking
- downloadable Parquet artifacts for larger datasets
- audit trail visible in admin
- multi-workspace support from day one
- plugin-style provider architecture for future licensed data vendors

## 21. Key Decisions to Lock Early

- internal/private tool vs public/commercial product
- single-workspace launch vs team collaboration launch
- whether object storage is required on day one or can be deferred briefly
- whether Yahoo remains acceptable beyond staging
- whether alerts should be email-only first or also support Slack/webhooks

## 22. Recommended MVP Acceptance Criteria

- A user can sign in, create or upload a universe, and run a screen from the web UI.
- A user can run a backtest from the web UI and inspect summary, trades, and equity curve.
- Long-running jobs run in Celery and never block API requests.
- Results persist in Postgres and large artifacts persist in object storage.
- The entire stack boots with Docker Compose.
- Staging and production environments use the same container topology.
- Operational users can inspect runs, schedules, and failures in Django admin.

## 23. Official References Used For This Plan

- Django deployment checklist: https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/
- Django ASGI deployment: https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
- Celery with Django: https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html
- Celery periodic tasks: https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html
- Docker Compose quickstart: https://docs.docker.com/compose/gettingstarted/
- Next.js self-hosting guide: https://nextjs.org/docs/app/guides/self-hosting
- PostgreSQL JSON/JSONB docs: https://www.postgresql.org/docs/current/datatype-json.html
- Django REST Framework docs: https://www.django-rest-framework.org/
