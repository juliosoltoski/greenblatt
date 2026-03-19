# Greenblatt Magic Formula Engine

Python CLI for screening and simulating Joel Greenblatt's Magic Formula strategy with pluggable market data providers.

## Documentation Map

- [technical_requirements.md](/home/jsoltoski/greenblatt/technical_requirements.md): investment logic, provider constraints, and functional baseline
- [product_plan.md](/home/jsoltoski/greenblatt/product_plan.md): product shape, architecture, and system design reference
- [implementation_plan.md](/home/jsoltoski/greenblatt/implementation_plan.md): the original M0-M10 execution roadmap, now completed
- [nice_to_have_implementation_plan.md](/home/jsoltoski/greenblatt/nice_to_have_implementation_plan.md): active post-M10 roadmap for product polish, UX, and deferred enhancements
- [contributor_guide.md](/home/jsoltoski/greenblatt/contributor_guide.md): where to change what across the shared core, backend, frontend, and infra
- [manual_smoke_test_guide.md](/home/jsoltoski/greenblatt/manual_smoke_test_guide.md): consolidated manual verification paths for local and staging-oriented checks
- [release_notes.md](/home/jsoltoski/greenblatt/release_notes.md): release-note convention and the latest shipped notes

## Status Snapshot

- Milestones `M0` through `M10` are implemented.
- The current focus should shift from core platform delivery to UX simplification, workflow polish, collaboration, and documentation quality.
- Public-cloud infrastructure and full live deployment should be planned in a separate future document rather than folded into the application roadmap.

## Features

- Current Magic Formula screening using EBIT, return on capital, and earnings yield.
- Mandatory exclusions for financials, utilities, and ADRs.
- Optional 6-month momentum modes: `none`, `overlay`, and `filter`.
- Tax-aware 51/53 week sell rules for simulation.
- Multi-provider market data layer with Yahoo Finance by default, optional Alpha Vantage support, and provider failover.
- Built-in universe profiles for a broad US screen and several starter international watchlists.

## Installation

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
```

All examples below assume the `greenblatt` console script is available after installation. If you prefer running the module directly, replace `greenblatt` with `PYTHONPATH=src python -m greenblatt.cli`.

## Web App

Milestones `M0` through `M10` now provide a runnable web platform alongside the CLI project:

- Django backend in [`backend/`](/home/jsoltoski/greenblatt/backend)
- Next.js frontend in [`frontend/`](/home/jsoltoski/greenblatt/frontend)
- Docker Compose stack in [`compose.yml`](/home/jsoltoski/greenblatt/compose.yml) and [`compose.dev.yml`](/home/jsoltoski/greenblatt/compose.dev.yml)
- Caddy reverse proxy in [`infra/caddy/Caddyfile`](/home/jsoltoski/greenblatt/infra/caddy/Caddyfile)

Bootstrap it locally with:

```bash
cp .env.example .env
docker compose -f compose.yml -f compose.dev.yml up --build
```

Useful URLs:

- `http://localhost:8080/` - frontend placeholder
- `http://localhost:8080/login` - sign-in page
- `http://localhost:8080/app` - protected app shell
- `http://localhost:8080/app/jobs` - Celery smoke-job launcher with live timeline streaming, cancel, and retry
- `http://localhost:8080/app/screens` - real screening launcher and persisted result review
- `http://localhost:8080/app/backtests` - persisted backtest launcher with equity curve and trade review
- `http://localhost:8080/app/templates` - reusable screen and backtest templates
- `http://localhost:8080/app/history` - prior run history with compare and template actions
- `http://localhost:8080/app/collaboration` - workspace activity feed and curated collections
- `http://localhost:8080/app/schedules` - recurring template schedules backed by `django-celery-beat`
- `http://localhost:8080/app/alerts` - alert routing, digests, workspace defaults, and recent delivery history
- `http://localhost:8080/health/live/` - backend liveness
- `http://localhost:8080/health/ready/` - backend readiness
- `http://localhost:9001/` - MinIO console

Local Redis is published on host port `6380` by default so it does not conflict with a Redis instance already running on `6379`.

To access the authenticated frontend, create a Django user first:

```bash
docker compose -f compose.yml -f compose.dev.yml exec backend python manage.py createsuperuser
```

Each new Django user automatically gets a personal workspace and an owner membership.

Email notifications default to Django's console backend in local development. To deliver real email,
set the SMTP-related variables from [.env.example](/home/jsoltoski/greenblatt/.env.example) before starting the stack.

Collaboration and sharing now include:

- comments and collections for templates, screen runs, and backtest runs
- read-only share links under `/shared/<token>`
- review states for templates and schedules
- workspace activity feed at `/app/collaboration`

Notification UX now includes:

- workspace-level email, Slack webhook, generic webhook, and digest preferences
- user-level channel opt-in controls
- live SSE job updates on the jobs dashboard and run detail pages
- digest delivery through the hourly beat task `automation.send_notification_digests`

Provider selection for the web stack is environment-driven:

```bash
MARKET_DATA_PROVIDER=yahoo
MARKET_DATA_PROVIDER_FALLBACK=alpha_vantage
ALPHA_VANTAGE_API_KEY=your-key-here
```

Provider status is available to authenticated users at `GET /api/v1/providers/`.
Add `?probe=true` to run live upstream checks instead of config-only checks.

Manual verification is now consolidated in [manual_smoke_test_guide.md](/home/jsoltoski/greenblatt/manual_smoke_test_guide.md).
Use that file for the end-to-end paths covering auth, universes, screens, backtests, templates, history, jobs, schedules, alerts, providers, and staging-oriented checks.

To clean up orphaned filesystem artifacts that are no longer referenced by uploads or run exports:

```bash
docker compose -f compose.yml -f compose.dev.yml exec backend \
  python manage.py cleanup_artifacts --dry-run
```

## Production Hardening

Milestone `M9` adds the staging and production hardening layer:

- structured backend and worker logs with request/job correlation ids
- optional Sentry wiring for Django and Celery
- Prometheus-format metrics at `GET /metrics/`
- API throttling and per-workspace async concurrency limits
- staging deployment, backup, smoke-test, and rollback scripts under [`infra/scripts/`](/home/jsoltoski/greenblatt/infra/scripts)
- a staging Compose override in [`infra/compose.staging.yml`](/home/jsoltoski/greenblatt/infra/compose.staging.yml)
- an operations runbook in [`infra/operations.md`](/home/jsoltoski/greenblatt/infra/operations.md)

Metrics can be protected by setting `METRICS_AUTH_TOKEN`. When configured, send it as either:

- `Authorization: Bearer <token>`
- `X-Metrics-Token: <token>`

To prepare a staging env file:

```bash
cp .env.staging.example .env.staging
```

To deploy staging from immutable images:

```bash
BACKEND_IMAGE=ghcr.io/<owner>/greenblatt-backend:<sha> \
FRONTEND_IMAGE=ghcr.io/<owner>/greenblatt-frontend:<sha> \
ENV_FILE=.env.staging \
./infra/scripts/deploy_staging.sh
```

To back up or restore staging:

```bash
ENV_FILE=.env.staging ./infra/scripts/backup_postgres.sh
ENV_FILE=.env.staging ./infra/scripts/backup_artifacts.sh
FORCE=true ENV_FILE=.env.staging ./infra/scripts/restore_postgres.sh backups/postgres-<timestamp>.sql.gz
FORCE=true ENV_FILE=.env.staging ./infra/scripts/restore_artifacts.sh backups/artifacts-<timestamp>.tar.gz
```

To load-test a realistic saved screen or backtest template:

```bash
docker compose -f compose.yml -f compose.dev.yml exec backend \
  python manage.py loadtest_runs --template-id 1 --launch-count 5 --wait --poll-interval 5
```

## Quick Start

```bash
greenblatt providers
greenblatt universes
greenblatt screen --profile us_top_3000 --candidate-limit 250 --top 25 --output results/us_top_25.csv
greenblatt simulate --profile eu_benelux_nordic --start 2024-01-01 --end 2025-12-31 --positions 10 --output results/eu_backtest
```

## Built-In Universes

Use `greenblatt universes` to list the bundled profiles:

- `us_top_3000`: broad US listed equity universe ranked by market cap
- `eu_benelux_nordic`: Benelux and Nordic starter watchlist
- `india_nifty100`: India starter watchlist
- `china_hk`: Shanghai, Shenzhen, and Hong Kong starter watchlist
- `sector_tech`: global technology-focused starter list
- `sector_healthcare`: global healthcare-focused starter list

## CLI Overview

The CLI has four commands:

- `greenblatt universes`: list built-in universe profiles
- `greenblatt providers`: list available market data providers
- `greenblatt screen`: run a current Magic Formula ranking
- `greenblatt simulate`: run the tax-aware backtest engine

For `screen` and `simulate`, you must choose exactly one universe input:

- `--profile <name>`
- `--universe-file <path>`
- `--tickers AAPL,MSFT,NVDA`

## CLI Usage Examples

### List Available Universes

```bash
greenblatt universes
```

### List Available Providers

```bash
greenblatt providers
```

### Screening Examples

```bash
# Broad US screen, print the top 25 and save to CSV
greenblatt screen \
  --profile us_top_3000 \
  --candidate-limit 250 \
  --top 25 \
  --output results/us_top_25.csv

# Run a smaller US screen directly to stdout
greenblatt screen \
  --profile us_top_3000 \
  --candidate-limit 100 \
  --top 10

# Screen a bundled sector watchlist
greenblatt screen \
  --profile sector_tech \
  --top 15 \
  --output results/sector_tech_top_15.csv

# Screen a hand-picked ticker basket
greenblatt screen \
  --tickers AAPL,MSFT,GOOGL,META,NVDA,ADBE,CRM,ORCL \
  --top 5

# Screen a newline-delimited custom universe file
greenblatt screen \
  --universe-file my_watchlist.txt \
  --top 20 \
  --output results/my_watchlist_top_20.csv

# Use 6-month momentum as a tie-breaker on top of the base formula
greenblatt screen \
  --profile us_top_3000 \
  --candidate-limit 200 \
  --momentum-mode overlay \
  --top 25

# Filter out the bottom half of names by 6-month momentum before ranking
greenblatt screen \
  --profile us_top_3000 \
  --candidate-limit 200 \
  --momentum-mode filter \
  --top 25

# Restrict the universe to exact Yahoo sector labels and a minimum market cap
greenblatt screen \
  --profile us_top_3000 \
  --candidate-limit 500 \
  --sector Technology,Healthcare \
  --min-market-cap 10000000000 \
  --top 30

# Save both the ranked output and the excluded names with reasons
greenblatt screen \
  --profile sector_healthcare \
  --top 20 \
  --output results/healthcare_top_20.csv \
  --exclusions-output results/healthcare_exclusions.csv

# Force Alpha Vantage for a smaller watchlist screen
greenblatt screen \
  --tickers MSFT,AAPL,NVDA \
  --provider alpha_vantage \
  --top 3

# Use Yahoo first and Alpha Vantage only if Yahoo fails
greenblatt screen \
  --profile us_top_3000 \
  --candidate-limit 100 \
  --provider yahoo \
  --fallback-provider alpha_vantage \
  --top 15

# Force a live fundamentals refresh
greenblatt screen \
  --profile us_top_3000 \
  --candidate-limit 100 \
  --refresh-cache

# Bypass the persistent snapshot cache for one run
greenblatt screen \
  --profile us_top_3000 \
  --candidate-limit 100 \
  --no-cache

# Reuse cached fundamentals for up to 7 days
greenblatt screen \
  --profile us_top_3000 \
  --candidate-limit 250 \
  --cache-ttl-hours 168
```

### Simulation Examples

```bash
# Basic Benelux/Nordic backtest
greenblatt simulate \
  --profile eu_benelux_nordic \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --positions 10 \
  --output results/eu_backtest

# US backtest on a throttling-friendly candidate set
greenblatt simulate \
  --profile us_top_3000 \
  --candidate-limit 150 \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --positions 20 \
  --output results/us_backtest

# Run a small backtest against Alpha Vantage data
greenblatt simulate \
  --tickers MSFT,AAPL,NVDA \
  --provider alpha_vantage \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --positions 2 \
  --output results/av_backtest

# Use custom capital and compare against QQQ instead of the S&P 500
greenblatt simulate \
  --profile sector_tech \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --capital 250000 \
  --positions 12 \
  --benchmark QQQ \
  --output results/tech_backtest

# Apply the momentum overlay during each rebalance
greenblatt simulate \
  --profile us_top_3000 \
  --candidate-limit 200 \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --momentum-mode overlay \
  --output results/us_backtest_overlay

# Keep only top-half momentum names at each rebalance
greenblatt simulate \
  --profile us_top_3000 \
  --candidate-limit 200 \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --momentum-mode filter \
  --output results/us_backtest_filter

# Backtest a custom Europe watchlist file
greenblatt simulate \
  --universe-file europe_watchlist.txt \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --positions 15 \
  --output results/europe_watchlist_backtest

# Backtest a manually specified basket
greenblatt simulate \
  --tickers AAPL,MSFT,GOOGL,META,NVDA,ADBE,CRM,ORCL,AMD,NOW \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --positions 5 \
  --output results/manual_basket_backtest

# Restrict to large-cap technology names inside the US profile
greenblatt simulate \
  --profile us_top_3000 \
  --candidate-limit 300 \
  --sector Technology \
  --min-market-cap 5000000000 \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --output results/us_tech_largecap

# Refresh cached snapshots before a new backtest
greenblatt simulate \
  --profile china_hk \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --refresh-cache \
  --output results/china_hk_refresh
```

## Universe File Format

Custom universe files are simple newline-delimited ticker lists. Blank lines and comment lines beginning with `#` are ignored.

```text
# my_watchlist.txt
AAPL
MSFT
NVDA
ASML.AS
NOVO-B.CO
0700.HK
```

## Output Files

`greenblatt screen` always prints the ranked table to stdout. If you pass output flags, it can also write:

- `--output`: ranked screen results as CSV
- `--exclusions-output`: excluded tickers with exclusion reasons as CSV

`greenblatt simulate` writes a directory containing:

- `equity_curve.csv`
- `trades.csv`
- `trade_summary.csv`
- `review_targets.csv`
- `final_holdings.csv`
- `summary.json`

## Practical Notes

- Yahoo Finance does not provide clean point-in-time historical fundamentals. The backtester is built for rebalancing and tax logic, but live Yahoo runs use the latest available fundamentals as an approximation.
- Enterprise value uses reported market cap, debt, minority interest, preferred stock, and a cash proxy when Yahoo does not expose excess cash separately.
- Current fundamentals snapshots are cached locally under `~/.cache/greenblatt-magic/snapshots` by default.
- Alpha Vantage requires `ALPHA_VANTAGE_API_KEY` and is best suited to smaller universes because its free tier is rate-limited.
- When Yahoo is throttling or rejecting requests, reduce load with `--candidate-limit 100` or `--candidate-limit 250`, then retry later.
- The bundled international and sector universe files are starter lists. Replace them with fuller constituent files when you want broader coverage.
