# Implementation Plan: Greenblatt Web App

## 1. Purpose

This document turns `product_plan.md` into an execution plan that can be implemented incrementally without a risky rewrite.

The implementation strategy is:

- preserve the current CLI engine as the core domain layer
- build the web app in vertical slices
- keep every milestone runnable through Docker Compose
- land backend, worker, and frontend changes behind clear interfaces
- delay optional features until the core screen and backtest flows are stable

## 2. Delivery Principles

- Do not rewrite the current ranking and simulation logic unless tests prove a change is required.
- Keep the CLI operational throughout the migration because it is useful for regression checks and operational debugging.
- Prefer one thin service layer that both the CLI and Django can call.
- Implement the smallest end-to-end slice first: auth -> universe -> async screen -> results.
- Add backtesting only after the async job system, persistence model, and result UI pattern are already proven by screening.
- Use feature flags or route guards where needed so incomplete surfaces do not appear in the UI.

## 3. Definitions of Done

Every milestone is complete only when all of these are true:

- code is merged and documented
- tests for the new behavior exist and pass
- Docker Compose can run the affected services locally
- a manual smoke path is written down and verified
- admin/support visibility exists for the new backend objects

## 4. Recommended Milestone Order

| Milestone | Outcome | Effort | Depends On |
| --- | --- | --- | --- |
| M0 | repo/bootstrap and local platform skeleton | M | none |
| M1 | shared core service layer and regression safety | M | M0 |
| M2 | Django auth, workspaces, admin baseline | M | M0 |
| M3 | universes and ticker upload flow | M | M1, M2 |
| M4 | async job framework with Celery and Redis | M | M1, M2 |
| M5 | screen vertical slice end to end | L | M3, M4 |
| M6 | backtest vertical slice end to end | L | M5 |
| M7 | templates, exports, result history, run duplication | M | M5, M6 |
| M8 | schedules, notifications, alerts | M | M7 |
| M9 | production hardening, observability, CI/CD, staging | L | M5-M8 |
| M10 | provider expansion beyond Yahoo | M | M9 |

Effort is relative only:

- `S`: small
- `M`: medium
- `L`: large

## 5. Milestone Details

### M0. Platform Bootstrap

#### Goal

Create the repo structure and local runtime needed for all later work.

#### Tasks

- Create top-level app structure for `backend`, `frontend`, and `infra`.
- Add Dockerfiles for backend and frontend.
- Add `compose.yml` plus a dev override file.
- Add Postgres, Redis, MinIO, backend, frontend, worker, beat, and proxy service definitions.
- Add `.env.example` with all required environment variables.
- Add health endpoints and health checks.
- Add a basic Caddy config that routes `/api/*` and `/admin/*` to Django and `/` to Next.js.
- Add CI skeleton that installs dependencies, runs tests, and builds images.

#### Deliverables

- local stack boots with `docker compose up`
- backend health endpoint responds
- frontend placeholder page responds
- Postgres and Redis are reachable from the backend container

#### Exit criteria

- A new developer can boot the stack from scratch using only the repo docs.
- CI can build all defined images without manual steps.

### M1. Shared Core Service Layer

#### Goal

Keep the current engine reusable and put a stable interface between core logic and all app surfaces.

#### Tasks

- Extract or adapt the current `src/greenblatt` package into a reusable core import path.
- Define service-layer request/response objects for screens and backtests.
- Move CLI orchestration to call the new service layer instead of calling the provider/engine directly.
- Add regression tests that compare service-layer output to the current CLI expectations.
- Add serialization helpers to convert pandas-heavy outputs into structured result payloads that Django can persist.

#### Deliverables

- `ScreenService` contract
- `BacktestService` contract
- reusable universe resolution service
- CLI still works using the shared service layer

#### Exit criteria

- Existing screen/backtest tests still pass.
- The CLI remains functional with no user-facing behavior regressions.

### M2. Auth, Workspace, and Admin Baseline

#### Goal

Stand up the Django application foundation with authentication and permission boundaries.

#### Tasks

- Create Django project and app layout.
- Add Django REST Framework and base API routing.
- Implement session-based auth endpoints: login, logout, current user.
- Create `workspace` and `workspace_membership` models.
- Add role checks for `owner`, `admin`, `analyst`, and `viewer`.
- Register users, workspaces, and memberships in Django admin.
- Build a protected frontend app shell and login flow.

#### Deliverables

- authenticated API and frontend session
- workspace-scoped access control
- working Django admin for identity objects

#### Exit criteria

- A user can sign in, view their workspace context, and access protected app pages.
- Unauthorized users cannot access another workspace's resources.

### M3. Universe Management

#### Goal

Implement built-in and custom universe management before any real job execution.

#### Tasks

- Implement built-in universe profile read API from the existing profile definitions.
- Create `universe` and `universe_entry` models.
- Add manual ticker entry and newline-delimited file upload flows.
- Add parsing, normalization, and validation for ticker uploads.
- Persist uploaded source files as artifacts in object storage or a storage abstraction.
- Build frontend universe pages for create, list, detail, and preview.
- Add admin support for universes and uploaded files.

#### Deliverables

- universe CRUD
- built-in profile listing
- custom file upload and validation
- preview of resolved tickers

#### Exit criteria

- A user can create a custom universe and inspect the tickers before running research jobs.
- Invalid uploads return clear validation errors.

### M4. Async Job Framework

#### Goal

Introduce the background job system before wiring in real screening and backtesting work.

#### Tasks

- Add Celery app configuration and Redis broker wiring.
- Add `job_run` model and generic job status API.
- Implement a generic task wrapper that writes status transitions, timestamps, progress, and errors.
- Add job retry policy helpers for transient failures.
- Create a dummy background task for smoke testing from the API.
- Add worker and beat processes to Docker Compose.
- Expose admin views for jobs and failed job inspection.

#### Deliverables

- persisted job records
- pollable job status endpoint
- functioning Celery worker in local Compose

#### Exit criteria

- A test task can be launched from the API and observed from queued to completed in the UI.
- Failed tasks record useful error messages and stack traces in logs/admin.

### M5. Screening Vertical Slice

#### Goal

Deliver the first real product workflow end to end.

#### Tasks

- Add `screen_run`, `screen_result_row`, and `screen_exclusion` models.
- Implement the Django-side `ScreenService` orchestration using the shared core package.
- Create a Celery task that resolves a universe and runs a real screen.
- Persist ranked rows, exclusions, run summary, and generated export artifacts.
- Add screen creation, list, detail, results, and export API endpoints.
- Build frontend pages for launching a screen, polling status, and reviewing results.
- Add pagination, sorting, and CSV download.
- Add regression fixtures for representative screen outputs.

#### Deliverables

- working screen run flow from UI to worker to persisted results
- job progress UI
- results table and exclusions table
- export download

#### Exit criteria

- A user can launch a real screen from the web UI and see stored results after refresh or re-login.
- Result rows match the shared core engine outputs for the same inputs.

### M6. Backtesting Vertical Slice

#### Goal

Deliver the second real workflow using the already-proven async and persistence patterns.

#### Tasks

- Add `backtest_run`, `backtest_equity_point`, `backtest_trade`, `backtest_review_target`, and `backtest_final_holding` models.
- Implement the Django-side `BacktestService`.
- Create a Celery task for real backtest execution.
- Persist backtest summary, equity curve, trades, review targets, and final holdings.
- Add backtest creation, list, detail, and child-data API endpoints.
- Build frontend pages for launching a backtest and visualizing the result.
- Add charts for equity curve and benchmark curve.
- Add table views for trades, review targets, and final holdings.
- Add regression fixtures for representative backtest outputs.

#### Deliverables

- working backtest run flow end to end
- equity curve chart
- trade ledger and holdings views
- stored backtest artifacts

#### Exit criteria

- A user can launch a backtest from the UI and inspect summary, curve, and trades.
- The stored result shape is stable enough to support exports and comparisons later.

### M7. Templates, History, Exports, and Run Duplication

#### Goal

Improve usability after both primary research workflows exist.

#### Tasks

- Add `strategy_template` model and template CRUD APIs.
- Add "save this run as template" and "run again" actions.
- Add history pages for prior screen and backtest runs.
- Expand artifact support for CSV and JSON downloads.
- Add run duplication using prior config as a draft.
- Add initial result comparison view between runs.
- Add artifact retention and cleanup rules.

#### Deliverables

- reusable templates
- result history
- duplication of prior runs
- stable export system

#### Exit criteria

- Users can repeat common workflows without re-entering all parameters.
- Past runs remain discoverable and downloadable.

### M8. Scheduling, Notifications, and Alerts

#### Goal

Introduce recurring execution and basic proactive notifications.

#### Tasks

- Add `run_schedule`, `alert_rule`, and `notification_event` models.
- Add `django-celery-beat` configuration and admin integration.
- Implement recurring screen and backtest launches from saved templates.
- Implement job completion notifications.
- Add first notification destination, preferably email.
- Add basic alert rules such as "screen completed", "run failed", or "ticker entered top N".
- Add frontend schedule and alert management pages.

#### Deliverables

- recurring schedules
- completion notifications
- first alert rules

#### Exit criteria

- A user can schedule a saved template and receive a completion notification.
- Failed scheduled runs surface clearly in the UI and admin.

### M9. Production Hardening

#### Goal

Make the app safe to stage and deploy.

#### Tasks

- Add structured logging and request/job correlation ids.
- Add Sentry or equivalent error reporting.
- Add metrics for job counts, queue latency, provider failures, and run durations.
- Add API throttling and per-workspace concurrency limits.
- Add backup strategy for Postgres and object storage.
- Add release pipeline, staging deployment, smoke tests, and rollback instructions.
- Add security settings hardening and `check --deploy` validation.
- Review permissions in admin and API endpoints.
- Load-test the worker with realistic candidate sizes and backtest volumes.

#### Deliverables

- staging-ready deployment process
- observability baseline
- security and rate-limit hardening

#### Exit criteria

- The stack can be deployed to staging from CI using built images.
- Core operational metrics and error visibility exist before production exposure.

### M10. Provider Expansion

#### Goal

Reduce dependence on Yahoo and prove the provider abstraction works in production conditions.

#### Tasks

- Define the exact provider contract surface used by the web app.
- Add a second provider adapter behind the existing interface.
- Add provider selection in configuration.
- Verify result persistence remains provider-agnostic.
- Add provider health reporting and fallback behavior where appropriate.

#### Deliverables

- second provider adapter
- provider switch capability
- provider health visibility

#### Exit criteria

- The app can run the same workflow against more than one provider without changing frontend contracts or database schema.

## 6. Parallel Workstreams

Some work can proceed in parallel after the right prerequisites exist.

### After M0

- backend foundation work
- frontend shell and design system setup
- CI and Compose improvements

### After M2

- universe UI work can proceed in parallel with universe API work
- job framework work can proceed in parallel with admin setup and support tooling

### After M4

- frontend screen pages can be built against stubbed or mocked API responses while backend wires the real task
- export and artifact storage plumbing can start before backtests are complete

### After M5

- result comparison UI
- template system
- notification scaffolding

## 7. Suggested Ticket Breakdown

Use issue-sized tickets rather than trying to land milestones in one branch.

### Foundation tickets

- bootstrap Django project
- bootstrap Next.js app
- add base Compose stack
- add Caddy routing
- add Postgres and Redis wiring
- add health checks
- add CI image builds

### Core integration tickets

- define service-layer request objects
- wrap current screen engine
- wrap current backtest engine
- switch CLI to service layer
- add serialization helpers

### Auth and workspace tickets

- login/logout/current-user API
- workspace and membership models
- role-based permission helpers
- protected app shell

### Universe tickets

- built-in profile API
- custom universe models
- upload parsing and validation
- universe CRUD pages

### Job tickets

- `job_run` model
- Celery configuration
- generic task wrapper
- job status polling API
- worker admin pages

### Screen tickets

- screen models
- screen task
- screen create/list/detail API
- screen results page
- CSV export

### Backtest tickets

- backtest models
- backtest task
- backtest create/list/detail API
- equity curve chart
- trade and holdings views

### Scheduling and notifications tickets

- schedule model
- beat integration
- notification model
- email notifications
- alert rules

### Hardening tickets

- Sentry integration
- rate limits
- structured logs
- metrics
- backup scripts
- staging smoke tests

## 8. Testing Plan By Milestone

### M0-M2

- container boot smoke tests
- auth API tests
- permission tests
- workspace admin tests

### M3-M4

- universe parsing tests
- upload validation tests
- Celery task lifecycle tests
- job status API tests

### M5

- screen service tests
- screen task integration tests
- screen API tests
- UI smoke tests for launch and poll

### M6

- backtest service tests
- backtest task integration tests
- backtest API tests
- UI smoke tests for summary and charts

### M7-M9

- template and schedule tests
- notification tests
- artifact retention tests
- staging smoke and restore drills

## 9. Suggested Release Increments

Use these as realistic demo checkpoints:

- Increment 1: local stack boots, auth works, workspace exists
- Increment 2: universes can be created and previewed
- Increment 3: async screen run works from UI
- Increment 4: backtest works from UI
- Increment 5: templates, history, and exports work
- Increment 6: schedules and notifications work
- Increment 7: staging deployment and hardening are complete

## 10. Scope Control

Do not pull these into implementation before the core slices are complete:

- social login
- Slack/webhook alerts
- read-only share links
- multi-provider routing in the UI
- public landing pages
- billing
- real-time streaming status over SSE or WebSockets

These are useful, but they are not on the critical path to the first deployable version.

## 11. Immediate Next Step

Start with M0 and M1 together:

1. establish the app structure and Docker Compose skeleton
2. stand up Django, Next.js, Postgres, Redis, and Caddy
3. define the shared service-layer contracts around the current core engine
4. keep the CLI running against that service layer

This sequence reduces the largest architectural risk early and gives the rest of the implementation a stable base.
