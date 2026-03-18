# Contributor Guide

## Purpose

Use this file as the shortest path to "where should I make this change?"

The product now has four main layers:

- [`src/greenblatt/`](/home/jsoltoski/greenblatt/src/greenblatt): shared screening, backtesting, provider, and serialization logic used by both the CLI and the web app
- [`backend/`](/home/jsoltoski/greenblatt/backend): Django API, models, Celery tasks, admin, and operational endpoints
- [`frontend/`](/home/jsoltoski/greenblatt/frontend): Next.js UI for the authenticated web app
- [`infra/`](/home/jsoltoski/greenblatt/infra): Caddy, staging compose overrides, deploy scripts, backups, smoke scripts, and operations docs

## Which Layer Owns What

- Change investment logic, ranking math, simulation behavior, provider adapters, or CLI orchestration in [`src/greenblatt/`](/home/jsoltoski/greenblatt/src/greenblatt).
- Change persisted workflows, API contracts, Celery execution, or admin operations in [`backend/`](/home/jsoltoski/greenblatt/backend).
- Change navigation, launch forms, result review pages, or interaction design in [`frontend/`](/home/jsoltoski/greenblatt/frontend).
- Change local dev stack, staging deployment, backup, or reverse proxy behavior in [`compose.yml`](/home/jsoltoski/greenblatt/compose.yml), [`compose.dev.yml`](/home/jsoltoski/greenblatt/compose.dev.yml), and [`infra/`](/home/jsoltoski/greenblatt/infra).

## App-Specific Ownership

- Universe storage and parsing: [`backend/apps/universes/`](/home/jsoltoski/greenblatt/backend/apps/universes)
- Async job tracking and Celery glue: [`backend/apps/jobs/`](/home/jsoltoski/greenblatt/backend/apps/jobs)
- Screen workflows: [`backend/apps/screens/`](/home/jsoltoski/greenblatt/backend/apps/screens) and [`frontend/app/app/screens/`](/home/jsoltoski/greenblatt/frontend/app/app/screens)
- Backtest workflows: [`backend/apps/backtests/`](/home/jsoltoski/greenblatt/backend/apps/backtests) and [`frontend/app/app/backtests/`](/home/jsoltoski/greenblatt/frontend/app/app/backtests)
- Templates and history: [`backend/apps/strategy_templates/`](/home/jsoltoski/greenblatt/backend/apps/strategy_templates) and [`frontend/app/app/templates/`](/home/jsoltoski/greenblatt/frontend/app/app/templates)
- Automation, schedules, and alerts: [`backend/apps/automation/`](/home/jsoltoski/greenblatt/backend/apps/automation), [`frontend/app/app/schedules/`](/home/jsoltoski/greenblatt/frontend/app/app/schedules), and [`frontend/app/app/alerts/`](/home/jsoltoski/greenblatt/frontend/app/app/alerts)
- Shared auth/session and provider status UI: [`backend/apps/accounts/`](/home/jsoltoski/greenblatt/backend/apps/accounts), [`backend/apps/core/`](/home/jsoltoski/greenblatt/backend/apps/core), and [`frontend/lib/api.ts`](/home/jsoltoski/greenblatt/frontend/lib/api.ts)

## Common Change Routes

- New market-data provider or provider failover rule:
  Start in [`src/greenblatt/providers/`](/home/jsoltoski/greenblatt/src/greenblatt/providers), then wire defaults and diagnostics in [`backend/apps/core/`](/home/jsoltoski/greenblatt/backend/apps/core).

- New screen or backtest input:
  Update the shared request model in [`src/greenblatt/services.py`](/home/jsoltoski/greenblatt/src/greenblatt/services.py), then the backend API/service layer, then the matching frontend launch form.

- New result field or export artifact:
  Update backend persistence and presenters first, then extend the frontend API types and detail pages.

- New operator workflow:
  Check [`infra/operations.md`](/home/jsoltoski/greenblatt/infra/operations.md), [`infra/scripts/`](/home/jsoltoski/greenblatt/infra/scripts), and the Django admin registration for the relevant app.

## Local Development Loop

### CLI

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
pytest
```

### Web App

```bash
cp .env.example .env
docker compose -f compose.yml -f compose.dev.yml up --build
docker compose -f compose.yml -f compose.dev.yml exec backend python manage.py createsuperuser
```

## Verification Expectations

For most feature work:

- add or update automated tests in the owning layer
- update any affected API typing in [`frontend/lib/api.ts`](/home/jsoltoski/greenblatt/frontend/lib/api.ts)
- add or refresh the manual verification path in [manual_smoke_test_guide.md](/home/jsoltoski/greenblatt/manual_smoke_test_guide.md)
- record user-visible changes and operational notes in [release_notes.md](/home/jsoltoski/greenblatt/release_notes.md)

## Documentation Map

- [technical_requirements.md](/home/jsoltoski/greenblatt/technical_requirements.md): investment and functional baseline
- [product_plan.md](/home/jsoltoski/greenblatt/product_plan.md): product and architecture reference
- [implementation_plan.md](/home/jsoltoski/greenblatt/implementation_plan.md): completed M0-M10 delivery record
- [nice_to_have_implementation_plan.md](/home/jsoltoski/greenblatt/nice_to_have_implementation_plan.md): active follow-on roadmap
- [manual_smoke_test_guide.md](/home/jsoltoski/greenblatt/manual_smoke_test_guide.md): consolidated manual verification flows
- [release_notes.md](/home/jsoltoski/greenblatt/release_notes.md): release-note convention and current entries

## Later Planning Note

Keep public-cloud infrastructure design separate from feature planning.

When that work starts, create `cloud_infrastructure_plan.md` instead of expanding the existing product roadmap files.
