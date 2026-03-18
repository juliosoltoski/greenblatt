# Greenblatt Magic Formula Engine

Python CLI for screening and simulating Joel Greenblatt's Magic Formula strategy with Yahoo Finance data.

## Features

- Current Magic Formula screening using EBIT, return on capital, and earnings yield.
- Mandatory exclusions for financials, utilities, and ADRs.
- Optional 6-month momentum modes: `none`, `overlay`, and `filter`.
- Tax-aware 51/53 week sell rules for simulation.
- Yahoo-backed provider with `curl_cffi` browser impersonation, retries, and bulk price downloads via `yfinance`.
- Built-in universe profiles for a broad US screen and several starter international watchlists.

## Installation

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
```

All examples below assume the `greenblatt` console script is available after installation. If you prefer running the module directly, replace `greenblatt` with `PYTHONPATH=src python -m greenblatt.cli`.

## Web App Scaffold

Milestone `M0` now includes a runnable web-platform scaffold alongside the CLI project:

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
- `http://localhost:8080/app/jobs` - Celery smoke-job launcher and status polling UI
- `http://localhost:8080/app/screens` - real screening launcher and persisted result review
- `http://localhost:8080/app/backtests` - persisted backtest launcher with equity curve and trade review
- `http://localhost:8080/app/templates` - reusable screen and backtest templates
- `http://localhost:8080/app/history` - prior run history with compare and template actions
- `http://localhost:8080/app/schedules` - recurring template schedules backed by `django-celery-beat`
- `http://localhost:8080/app/alerts` - alert-rule management and recent notification delivery history
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

To smoke-test the async job pipeline after logging in:

1. Open `http://localhost:8080/app/jobs`.
2. Launch the default smoke job.
3. Watch the run move from `queued` to `running` to `succeeded`, or choose a failure mode to inspect retries and error capture.

To smoke-test the first real screening workflow:

1. Create or open a saved universe at `http://localhost:8080/app/universes`.
2. Open `http://localhost:8080/app/screens`.
3. Launch a screen from the saved universe.
4. Open the resulting screen detail page and verify the ranked rows, exclusions, and CSV export link.

To smoke-test the backtesting workflow:

1. Create or open a saved universe at `http://localhost:8080/app/universes`.
2. Open `http://localhost:8080/app/backtests`.
3. Launch a backtest with a small saved universe and a short date range.
4. Open the resulting backtest detail page and verify the equity curve, trade ledger, final holdings, review targets, and export download link.

To smoke-test M7 templates and history:

1. Launch at least one screen or backtest so the workspace has persisted runs.
2. Open `http://localhost:8080/app/history`.
3. Save one prior run as a template, then open `http://localhost:8080/app/templates`.
4. Use the template as a draft or launch it directly and verify a new run is created.
5. Select two runs of the same type in history and open the compare view.

To smoke-test M8 schedules and alerts:

1. Make sure your Django user has an email or set an explicit destination email in the forms.
2. Open `http://localhost:8080/app/templates` and confirm you have at least one saved template.
3. Open `http://localhost:8080/app/schedules` and create a recurring schedule from that template.
4. Use the schedule's `Run now` action to launch it immediately and confirm a new screen or backtest run is created.
5. Open `http://localhost:8080/app/alerts`, create either a `run failed`, `screen completed`, `backtest completed`, or `ticker entered top N` rule, then launch a matching run.
6. Verify the resulting notification event appears in the alerts page and, with real SMTP configured, is delivered by email.

To clean up orphaned filesystem artifacts that are no longer referenced by uploads or run exports:

```bash
docker compose -f compose.yml -f compose.dev.yml exec backend \
  python manage.py cleanup_artifacts --dry-run
```

## Quick Start

```bash
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

The CLI has three commands:

- `greenblatt universes`: list built-in universe profiles
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
- When Yahoo is throttling or rejecting requests, reduce load with `--candidate-limit 100` or `--candidate-limit 250`, then retry later.
- The bundled international and sector universe files are starter lists. Replace them with fuller constituent files when you want broader coverage.
