# Architecture

This document describes the current implementation of the Greenblatt application as it exists in this repository. It is intentionally code-first: when planning documents and running code differ, this document favors the running code.

## 1. Purpose And Scope

Greenblatt is a research workflow platform built around Joel Greenblatt-style value screening and tax-aware backtesting.

Today the app supports:

- multi-workspace research collaboration
- built-in and custom universes
- asynchronous screen runs
- asynchronous backtest runs
- reusable strategy templates
- recurring schedules backed by Celery Beat
- alerts and notification preferences
- collaboration features such as comments, collections, activity, and share links
- provider diagnostics and cache-warm operations
- a standalone CLI that uses the same core research engine as the backend

It does not execute trades. The system is positioned as a research and workflow platform, not a brokerage or live portfolio execution system.

## 2. System Overview

At a high level the system has three code layers:

1. `src/greenblatt`: reusable domain engine, providers, CLI, and orchestration primitives
2. `backend/`: Django + Django REST Framework + Celery application that persists data and exposes APIs
3. `frontend/`: Next.js App Router application that provides the user interface

Runtime topology:

```text
Browser
  |
  | HTTP, fetch, SSE
  v
Caddy reverse proxy (:8080)
  |-----------------------------> Next.js frontend (:3000)
  |                                 - public marketing/login/shared pages
  |                                 - authenticated app UI
  |
  |-----------------------------> Django API (:8000)
                                    - /api/v1/*
                                    - /health/*
                                    - /metrics
                                    - /admin (direct localhost redirect in Caddy)

Django API
  |
  | ORM / cache / task dispatch
  +--> PostgreSQL
  +--> Redis
  +--> artifact filesystem volume
  +--> external market data providers
  +--> email / webhook delivery targets

Celery worker
  |
  +--> runs screen, backtest, smoke, cache-warm, schedule, and digest tasks

Celery beat
  |
  +--> executes DB-backed periodic schedules
```

## 3. Repository Layout

| Path | Responsibility |
| --- | --- |
| `src/greenblatt/` | Shared domain engine, provider layer, CLI, universe profiles, screen/backtest orchestration |
| `backend/` | Django project, REST API, Celery tasks, persistence, auth, collaboration, automation |
| `frontend/` | Next.js frontend, route UI, typed API client, SSE hooks |
| `tests/` | Shared-core tests for the reusable Python package |
| `infra/` | Caddy config and operational notes |
| `compose.yml` | Main local runtime topology |
| `compose.dev.yml` | Development overrides with bind mounts and local dev servers |
| `results/` | Generated analysis outputs and artifacts from CLI or manual runs |
| top-level `*.md` plans | Product, implementation, commercial, staging, and operations planning docs |

## 4. Runtime Components

The default Docker Compose stack defines these services:

| Service | Role | Notes |
| --- | --- | --- |
| `postgres` | primary relational database | PostgreSQL 17, persisted via `postgres_data` |
| `redis` | Celery broker, Celery result backend, optional Django cache | persisted via `redis_data` |
| `minio` | future object-storage target | provisioned but not currently used by the artifact layer |
| `backend` | Django API server | serves REST, health, metrics, and admin |
| `worker` | Celery worker | executes async jobs with `--pool=solo` in compose |
| `beat` | Celery Beat scheduler | uses `django_celery_beat.schedulers:DatabaseScheduler` |
| `frontend` | Next.js application | serves app UI and frontend health route |
| `proxy` | Caddy reverse proxy | routes `/api`, `/health`, and `/metrics` to backend, everything else to frontend |

Important implementation details:

- In development, `compose.dev.yml` bind-mounts `backend/`, `src/`, and `frontend/`.
- The development backend command runs migrations and `sync_builtin_universes` before starting Django.
- The frontend health route is `GET /health`.
- Caddy redirects `/admin/*` to `http://localhost:8000{uri}` instead of reverse-proxying it.

## 5. Shared Domain Core

The reusable Python package in `src/greenblatt` is the architectural center of the product logic. Both the CLI and the Django backend call into it.

### 5.1 Domain Models

Core data structures live in `src/greenblatt/models.py` and include:

- `SecuritySnapshot`: raw provider fundamentals and metadata for one security
- `RankedSecurity`: enriched snapshot with ROC, EY, EV, ranks, and final score
- `ExclusionRecord`: why a security was screened out
- `ScreenConfig` and `ScreenResult`
- `Holding`, `Trade`, `BacktestConfig`, and `BacktestResult`

These dataclasses define the research domain independent of Django models or frontend types.

### 5.2 Screening Engine

`src/greenblatt/engine.py` implements the Magic Formula ranking logic:

- computes net working capital, enterprise value, return on capital, and earnings yield
- excludes ADRs, financials, and utilities by default
- supports sector allowlists and minimum market-cap filters
- supports momentum modes:
  - `none`
  - `overlay`
  - `filter`
- ranks by ROC and EY, then optionally incorporates momentum

This logic is pure domain logic. It does not know about Django, HTTP, or the frontend.

### 5.3 Backtesting Engine

`src/greenblatt/simulation.py` implements the tax-aware backtest engine:

- resolves review dates from a trading calendar
- screens the universe on each review date
- buys equal-weight replacements into open slots
- sells losers after 51 weeks
- sells winners after 53 weeks
- tracks cash, positions, equity, trades, review targets, trade summary, and optional benchmark comparison

The backtester reuses the screening engine instead of duplicating ranking logic.

### 5.4 Provider Layer

`src/greenblatt/services.py` and `src/greenblatt/providers/*` implement provider abstraction and orchestration.

Supported providers today:

- `yahoo`
- `alpha_vantage`

The provider layer supports:

- provider descriptors and health payloads
- normalized provider configuration payloads
- optional fallback providers through `FailoverProvider`
- cache controls: `use_cache`, `refresh_cache`, and `cache_ttl_hours`

Notable provider behavior:

- Yahoo is the default provider.
- Alpha Vantage requires an API key.
- Failover only triggers on recognized provider exceptions.
- Provider result payloads record the requested provider, fallback provider, resolved provider, and whether fallback was used.

### 5.5 Universe Resolution

`src/greenblatt/universe.py` provides built-in universe profiles.

There are two profile categories:

- packaged static lists, such as FTSE 100 or ASX 200
- live-data profiles, such as `us_top_3000` and U.S. sector universes resolved through provider data

This split matters because some universes can be refreshed without contacting a provider, while others require live provider access.

### 5.6 CLI

The `greenblatt` console script in `src/greenblatt/cli.py` exposes:

- `greenblatt universes`
- `greenblatt providers`
- `greenblatt screen`
- `greenblatt simulate`

The CLI is not a separate architecture branch. It is another entry point into the same shared domain services used by the web app.

## 6. Backend Architecture

The backend is a Django 5.2 application with Django REST Framework and Celery.

### 6.1 Cross-Cutting Backend Stack

Key backend technologies:

- Django for application structure, ORM, admin, auth, and management commands
- Django REST Framework for API views, serialization, permissions, throttling, and error responses
- Celery for asynchronous work
- `django-celery-beat` for persistent schedules
- PostgreSQL in deployed compose environments, SQLite fallback when `POSTGRES_HOST` is not set
- WhiteNoise for static-file serving
- Prometheus client for metrics
- optional Sentry integration

The backend uses session-based authentication, not JWT.

### 6.2 Backend App Map

| App | Responsibility |
| --- | --- |
| `apps.accounts` | login/logout/CSRF/current user/account settings |
| `apps.workspaces` | workspace tenancy, membership, role checks |
| `apps.universes` | custom/built-in/uploaded universes, ticker validation, upload storage |
| `apps.jobs` | generic async job tracking, events, retry, cancellation, smoke jobs, SSE stream |
| `apps.screens` | screen-run persistence, exports, API, Celery task dispatch |
| `apps.backtests` | backtest-run persistence, equity/trade persistence, exports, Celery task dispatch |
| `apps.strategy_templates` | reusable saved workflow definitions and launch helpers |
| `apps.automation` | recurring schedules, alert rules, notification preferences, digest delivery |
| `apps.collaboration` | comments, collections, activity events, share links, public shared-resource API |
| `apps.core` | health, metrics, provider diagnostics, provider cache warm, middleware, logging, throttling, Sentry |

### 6.3 API Surface

All primary APIs live under `/api/v1/`.

Top-level route groups:

- `/api/v1/auth/`
- `/api/v1/automation/`
- `/api/v1/backtests/`
- `/api/v1/collaboration/`
- `/api/v1/jobs/`
- `/api/v1/providers/`
- `/api/v1/screens/`
- `/api/v1/strategy-templates/`
- `/api/v1/universe-profiles/`
- `/api/v1/universes/`
- `/api/v1/workspaces/`
- `/api/v1/shared/<token>/`

Operational routes outside `/api/v1/`:

- `/health/live/`
- `/health/ready/`
- `/api/health/`
- `/metrics/`

### 6.4 Backend Architectural Style

The backend follows a pragmatic layered style rather than strict hexagonal architecture:

- models hold persistent state
- serializers validate request payloads
- services own orchestration, launch, and persistence rules
- presenters turn models into API response payloads
- API views stay relatively thin

This pattern is consistent across screens, backtests, templates, automation, and collaboration.

## 7. Data Model And Tenancy

The system is workspace-centric. Almost every business entity hangs off a `Workspace`.

### 7.1 Identity And Access

Core identity objects:

- Django built-in user model
- `Workspace`
- `WorkspaceMembership`

Supported roles:

- `viewer`
- `analyst`
- `admin`
- `owner`

Role enforcement is centralized through helpers in `apps.workspaces.access` and `apps.workspaces.permissions`.

### 7.2 Research Entities

Universe layer:

- `Universe`
- `UniverseEntry`
- `UniverseUpload`

Screen layer:

- `ScreenRun`
- `ScreenResultRow`
- `ScreenExclusion`

Backtest layer:

- `BacktestRun`
- `BacktestEquityPoint`
- `BacktestTrade`
- `BacktestReviewTarget`
- `BacktestFinalHolding`

Template layer:

- `StrategyTemplate`

### 7.3 Automation Entities

- `RunSchedule`
- `AlertRule`
- `NotificationEvent`
- `WorkspaceNotificationPreference`
- `UserNotificationPreference`

`RunSchedule` is mirrored to `django_celery_beat` `PeriodicTask` records by the automation service layer.

### 7.4 Collaboration Entities

- `ResourceComment`
- `ResourceShareLink`
- `WorkspaceCollection`
- `WorkspaceCollectionItem`
- `ActivityEvent`

Shareable resource kinds are:

- strategy template
- run schedule
- screen run
- backtest run

### 7.5 Generic Job Entities

- `JobRun`
- `JobEvent`

`JobRun` is the common async envelope around screens, backtests, smoke checks, provider cache warm jobs, and scheduled launches.

### 7.6 Relationship Summary

Conceptually:

```text
User
  -> WorkspaceMembership
  -> Workspace
       -> Universe -> UniverseEntry / UniverseUpload
       -> StrategyTemplate
       -> JobRun -> JobEvent
       -> ScreenRun -> ScreenResultRow / ScreenExclusion
       -> BacktestRun -> EquityPoint / Trade / ReviewTarget / FinalHolding
       -> RunSchedule
       -> AlertRule -> NotificationEvent
       -> WorkspaceCollection -> WorkspaceCollectionItem
       -> ResourceComment
       -> ResourceShareLink
       -> ActivityEvent
```

## 8. Frontend Architecture

The frontend is a Next.js 16 + React 19 + TypeScript application using the App Router.

### 8.1 Frontend Structure

Key route surfaces:

- `/` public landing page
- `/login` session login page
- `/app/*` authenticated application shell
- `/shared/[token]` public or member-restricted shared resource page
- `/health` frontend health endpoint

The authenticated app shell is wrapped by `frontend/app/app/layout.tsx` and `AppChrome`.

### 8.2 Data Fetching Model

The frontend uses a typed fetch client in `frontend/lib/api.ts`.

Important characteristics:

- same-origin `fetch`
- backend base path defaults to `/api`
- explicit CSRF bootstrap via `/api/v1/auth/csrf/`
- typed request/response payloads for all major domains
- no dedicated client-side query library such as React Query
- state is handled with route-level/component-level React state

This makes the frontend relatively thin and straightforward, but also means caching, invalidation, and optimistic updates are implemented manually where needed.

### 8.3 Real-Time Updates

Job progress uses server-sent events, not WebSockets.

- frontend hook: `frontend/lib/jobStream.ts`
- backend endpoint: `/api/v1/jobs/<job_id>/stream/`

The browser opens an `EventSource`, listens for `job` and `job_event` events, and updates local UI state.

### 8.4 Client Persistence

Some UI-only preferences are stored in local storage through helper modules such as `frontend/lib/viewPreferences.ts`.

### 8.5 Frontend Role In The Overall System

The frontend does not contain the research logic. It is a typed UI layer over backend APIs plus SSE status updates.

## 9. Key End-To-End Flows

### 9.1 Authentication And Workspace Resolution

1. The browser requests a CSRF cookie from `/api/v1/auth/csrf/`.
2. Login posts credentials to `/api/v1/auth/login/`.
3. Django authenticates with session auth and sets a session cookie.
4. The frontend calls `/api/v1/auth/me/` to get the current user and workspace list.
5. Most data APIs either accept `workspace_id` explicitly or default to the first accessible workspace.

### 9.2 Universe Creation And Sync

Universes come from one of three sources:

- built-in profile
- manual ticker text
- uploaded text file

Flow:

1. The frontend posts universe input to the universes API.
2. The backend validates ticker syntax and limits.
3. Uploaded files are persisted through `ArtifactStorage`.
4. Built-in profiles are resolved either from packaged lists or from live provider data.
5. `Universe` and `UniverseEntry` rows are written to PostgreSQL.

Built-in profile sync is also available through the `sync_builtin_universes` management command and is run automatically in the dev backend startup flow.

### 9.3 Screen Run

1. The frontend submits a screen launch request with universe, filters, and provider settings.
2. The backend service validates access and configuration.
3. A `JobRun` and `ScreenRun` are created.
4. The backend enqueues Celery task `screens.run_screen_job`.
5. The worker resolves the provider and universe, runs the shared domain screen service, stores rows and exclusions, and writes export artifacts.
6. The frontend watches job progress over SSE and later loads the persisted run detail.

Outputs:

- ranked result rows
- exclusion rows
- JSON export endpoint
- optional CSV export artifact
- provider summary metadata

### 9.4 Backtest Run

1. The frontend submits a backtest launch request with dates, portfolio settings, benchmark, and provider settings.
2. The backend persists `JobRun` and `BacktestRun`.
3. Celery task `backtests.run_backtest_job` runs asynchronously.
4. The worker reuses the shared backtesting engine, persists curve points, trades, review targets, and final holdings, and stores artifacts.
5. The UI consumes summary and detail data from the persisted run.

Outputs:

- equity curve
- trade ledger
- trade summary
- review targets
- final holdings
- JSON export endpoint
- ZIP artifact when generated

### 9.5 Templates And Scheduled Runs

Templates capture normalized screen or backtest configuration and allow future launches without reconstructing payloads from scratch.

Flow:

1. A user creates or derives a `StrategyTemplate`.
2. A `RunSchedule` references that template and desired cadence.
3. The automation service mirrors that schedule into a Celery Beat `PeriodicTask`.
4. Beat triggers `automation.run_scheduled_template`.
5. The backend launches a new screen or backtest run through the same service layer used for manual launches.

This keeps manual and scheduled launches on one code path.

### 9.6 Alerts And Notifications

Alerts are workspace-scoped rules that react to workflow events such as:

- screen completed
- backtest completed
- run failed
- ticker entered top N

Delivery channels currently modeled:

- email
- Slack webhook
- generic webhook
- digest

Notification state is persisted in `NotificationEvent`, which makes delivery observable and auditable.

### 9.7 Collaboration And Sharing

Collaboration features operate on persisted research resources.

Supported behaviors:

- comments on resources
- collections of resources
- workspace activity feed
- share links

Share links can be:

- token-accessible
- restricted to workspace members

The public shared-resource endpoint is `/api/v1/shared/<token>/`.

Important implementation detail:

- shared screen and backtest payloads are bounded previews, not complete raw datasets

### 9.8 Provider Diagnostics And Cache Warm

The app exposes provider visibility as a first-class operational feature.

Capabilities:

- list configured providers and health
- probe providers on demand
- inspect workspace-specific provider diagnostics
- launch cache-warm jobs for a universe sample

Provider cache warm launches through the same generic job infrastructure as research runs.

## 10. Asynchronous Execution Model

Async work is built around `JobRun`, `JobEvent`, and `TrackedJobTask`.

### 10.1 Job Lifecycle

Supported job states:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `partial_failed`

The common task base:

- marks jobs running
- emits progress events
- honors cancellation requests
- retries retryable failures
- records failure metadata and tracebacks
- records provider-failure metadata when applicable
- marks jobs terminal on completion or cancellation

### 10.2 Celery Tasks In Use

Configured Celery routes include:

- `screens.run_screen_job`
- `backtests.run_backtest_job`
- `jobs.run_smoke_job`
- `core.run_provider_cache_warm_job`
- `automation.run_scheduled_template`
- `automation.send_notification_digests`

### 10.3 Concurrency And Throttling

Two separate guardrails exist:

- DRF rate throttles on HTTP endpoints
- workspace concurrency limits on async launches

Default throttle scopes:

- burst
- anon
- login
- launch
- mutation
- export

Default workspace concurrency limits:

- 8 total active jobs
- 2 active research jobs (`screen_run`, `backtest_run`)
- 3 active smoke jobs

Concurrency rejections are also recorded as Prometheus counters.

### 10.4 SSE Implementation Model

SSE is implemented with `StreamingHttpResponse`.

The stream:

- immediately emits a `retry` hint
- polls the latest job and new events once per second
- closes after the job is terminal or after roughly 25 seconds

The frontend is expected to reconnect if it still needs updates.

## 11. Storage Strategy

### 11.1 Relational Storage

PostgreSQL is the primary persistent store in the compose environment.

It holds:

- workspace and user relationships
- universes and entries
- runs and job metadata
- templates
- schedules
- alerts and notification history
- collaboration records
- `django-celery-beat` schedule state

If `POSTGRES_HOST` is absent, the backend falls back to SQLite for local non-compose usage.

### 11.2 Redis

Redis is used for:

- Celery broker
- Celery result backend
- optional Django cache backend

### 11.3 Artifact Storage

The backend has an artifact abstraction in `apps.universes.services.ArtifactStorage`, but only the `filesystem` backend is implemented today.

Filesystem artifacts currently cover:

- uploaded universe source files
- screen exports
- backtest exports

Operational cleanup is handled by the `cleanup_artifacts` management command, which removes orphaned filesystem artifacts after a retention window.

### 11.4 Provider Caches

Provider-level market data caches are separate from app artifact storage.

For example, the Yahoo provider uses a filesystem cache under the local user cache directory. This means provider cache management and artifact lifecycle management are related but not the same subsystem.

### 11.5 MinIO Status

MinIO is provisioned in Docker Compose, and related environment variables exist, but the application artifact layer does not yet write to object storage. S3-style storage is prepared infrastructure, not current behavior.

## 12. Security And Access Control

### 12.1 Auth Model

The app uses:

- Django session authentication
- CSRF protection on mutating requests
- same-origin cookies

There is no token-based SPA auth layer in the current implementation.

### 12.2 Role Model

Workspace access is role-based:

- `viewer`: read-level participation
- `analyst`: can launch jobs and manage most research workflow objects
- `admin`: elevated management within a workspace
- `owner`: highest workspace role

Typical minimum roles:

| Action | Minimum role |
| --- | --- |
| view workspace resources | `viewer` |
| comment on resources | `viewer` |
| launch screens/backtests/jobs | `analyst` |
| cancel/retry jobs | `analyst` |
| create share links | `analyst` |
| manage collections | `analyst` |
| delete others' comments | `admin` |

### 12.3 Shared Resources

Shared resources deliberately bypass the normal authenticated app shell, but they still have access control:

- inactive or expired links return not found
- `workspace_member` share links require an authenticated user with workspace membership
- token links can be viewed by anyone with the token

### 12.4 Metrics Protection

`/metrics/` can be protected with `METRICS_AUTH_TOKEN`.

If configured, the token must be supplied either:

- as `X-Metrics-Token`
- or as `Authorization: Bearer <token>`

### 12.5 Security Headers And Cookies

The backend sets and supports:

- secure cookie options
- `SameSite`
- `HttpOnly` session cookie
- HSTS-related settings
- `X_FRAME_OPTIONS`
- content-type sniffing protection
- referrer and COOP settings

These are environment-driven and can be hardened outside development.

## 13. Observability And Operations

### 13.1 Request Context

`RequestContextMiddleware` creates per-request observability context including:

- request ID
- correlation ID
- workspace ID when present
- user ID
- path
- method

The request ID is returned in the `X-Request-ID` response header.

Celery tasks propagate job-level observability context when they begin running.

### 13.2 Metrics

Prometheus metrics include:

- HTTP request counts
- HTTP request latency
- API throttle rejections
- workspace concurrency rejections
- persisted job counts
- active job counts
- queue latency and run duration aggregates
- provider-related job failure counts
- notification event counts

### 13.3 Health Endpoints

- `GET /health/live/`: backend liveness
- `GET /health/ready/`: backend readiness with DB and Redis checks
- `GET /api/health/`: alias of readiness
- `GET /health`: frontend health

### 13.4 Logging And Error Monitoring

Logging is configured through `apps.core.logging`.

Important characteristics:

- configurable log level
- JSON logging by default outside debug mode
- optional Sentry initialization with DSN, release, environment, tracing, and profiles sample rates

### 13.5 Operational Support Surfaces

There are two notable operator-oriented surfaces:

- Django admin
- provider diagnostics / cache warm / job monitoring pages in the product UI

Staff users also receive an expanded support overview in account settings, including recent failure counts and recent failed jobs.

### 13.6 Useful Management Commands

- `sync_builtin_universes`
- `cleanup_artifacts`

These commands are part of the real operational architecture, not just developer conveniences.

## 14. Testing And Quality Gates

Testing is split across multiple layers:

- `tests/` covers shared package behavior such as engine, providers, services, and simulation
- `backend/apps/*/tests.py` covers API, service, model, and task behavior per Django app
- frontend safety currently relies on TypeScript and production build checks rather than a dedicated frontend test suite

Notable quality characteristics:

- the domain engine is testable independently of the web stack
- backend domain apps are testable through Django's ORM and API views
- frontend type-checking catches API drift in many cases because the client is strongly typed

Current gap:

- there is no material frontend unit/integration test suite in the repository today

## 15. Current Constraints And Intentional Tradeoffs

Several architectural choices are deliberately simple at this stage:

- session auth instead of token auth
- server-sent events instead of WebSockets
- manual typed fetch client instead of a heavier frontend data library
- filesystem artifact storage instead of S3-backed object storage
- Caddy-based single-domain local routing instead of separate public API/frontend origins
- one shared Celery queue in compose instead of dedicated workload queues

Important implementation realities:

- MinIO is provisioned but not yet integrated into artifact writes
- social login and billing are feature-flag placeholders, not complete subsystems
- the product plan may mention additional frontend or infrastructure tools that are not present in the current codebase
- the UI exposes operator tooling, but the core product remains a research system rather than an execution platform

## 16. Extension Guidance

### 16.1 Adding A New Market Data Provider

Typical changes belong in:

- `src/greenblatt/providers/`
- `src/greenblatt/services.py`
- backend provider config/presenter helpers if new UI fields are needed
- frontend provider diagnostics and launch forms if the provider should be user-selectable

The provider contract should stay behind `MarketDataProvider`.

### 16.2 Adding A New Research Workflow Type

A new workflow should normally include:

- a persistent run model
- optional result row models
- a service layer
- a Celery task
- presenters and serializers
- API views and URLs
- frontend typed API bindings
- frontend hub/detail pages
- collaboration resource support if it should be commentable/shareable

The existing screen/backtest/template pattern is the reference design.

### 16.3 Upgrading Artifact Storage

The cleanest path is to extend `ArtifactStorage` with a real object-storage backend and keep the rest of the application speaking in terms of:

- `storage_backend`
- `storage_key`
- checksum
- size

That would preserve the existing model contracts while changing the underlying persistence mechanism.

## 17. Summary

Greenblatt is architected as a workspace-centric research platform with:

- a reusable Python research core
- a Django API and Celery execution layer
- a thin Next.js frontend
- PostgreSQL and Redis as the persistence backbone
- filesystem artifacts
- provider integrations with optional failover
- collaboration and automation built on top of persisted research objects

The architecture is intentionally practical. Shared domain logic lives in one place, backend services own orchestration and persistence, and the frontend stays close to the API. The main unfinished edges are object storage integration, richer frontend infrastructure, and the broader commercial/platform capabilities already sketched in the planning documents.
