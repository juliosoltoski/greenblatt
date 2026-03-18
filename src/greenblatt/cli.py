from __future__ import annotations

import argparse
import json
from pathlib import Path

from greenblatt.models import BacktestConfig, ScreenConfig
from greenblatt.services import BacktestRequest, BacktestService, ProviderConfig, ScreenRequest, ScreenService, UniverseRequest, UniverseService
from greenblatt.utils import parse_date


def main() -> None:
    parser = argparse.ArgumentParser(description="Greenblatt Magic Formula screener and simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    universes_parser = subparsers.add_parser("universes", help="List built-in universe profiles")
    universes_parser.set_defaults(func=_run_universes)

    screen_parser = subparsers.add_parser("screen", help="Run a current Magic Formula screen")
    _add_universe_arguments(screen_parser)
    screen_parser.add_argument("--top", type=int, default=30, help="Number of ranked names to return")
    screen_parser.add_argument(
        "--candidate-limit",
        type=int,
        help="Optional cap on the resolved universe before fundamentals are fetched",
    )
    screen_parser.add_argument(
        "--momentum-mode",
        choices=["none", "overlay", "filter"],
        default="none",
        help="How to apply the 6-month momentum overlay",
    )
    screen_parser.add_argument("--sector", help="Optional sector allowlist, comma separated")
    screen_parser.add_argument("--min-market-cap", type=float, help="Minimum market cap filter")
    _add_cache_arguments(screen_parser)
    screen_parser.add_argument("--output", help="Write ranked screen results to CSV")
    screen_parser.add_argument("--exclusions-output", help="Write excluded tickers to CSV")
    screen_parser.set_defaults(func=_run_screen)

    simulate_parser = subparsers.add_parser("simulate", help="Run the tax-aware backtest engine")
    _add_universe_arguments(simulate_parser)
    simulate_parser.add_argument("--start", required=True, help="Simulation start date (YYYY-MM-DD)")
    simulate_parser.add_argument("--end", required=True, help="Simulation end date (YYYY-MM-DD)")
    simulate_parser.add_argument("--capital", type=float, default=100_000.0, help="Initial capital")
    simulate_parser.add_argument("--positions", type=int, default=20, help="Number of equal-weight positions")
    simulate_parser.add_argument(
        "--candidate-limit",
        type=int,
        help="Optional cap on the resolved universe before simulation data is fetched",
    )
    simulate_parser.add_argument(
        "--momentum-mode",
        choices=["none", "overlay", "filter"],
        default="none",
        help="How to apply the 6-month momentum overlay during rebalances",
    )
    simulate_parser.add_argument("--sector", help="Optional sector allowlist, comma separated")
    simulate_parser.add_argument("--min-market-cap", type=float, help="Minimum market cap filter")
    simulate_parser.add_argument("--benchmark", default="^GSPC", help="Benchmark ticker")
    _add_cache_arguments(simulate_parser)
    simulate_parser.add_argument("--output", required=True, help="Directory for equity curve, trades, and summary")
    simulate_parser.set_defaults(func=_run_simulate)

    args = parser.parse_args()
    try:
        args.func(args)
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")


def _run_universes(_: argparse.Namespace) -> None:
    for profile in UniverseService().list_profiles():
        print(f"{profile.key}: {profile.description} [{profile.source}]")


def _run_screen(args: argparse.Namespace) -> None:
    response = ScreenService().run(
        _build_screen_request(args),
    )
    frame = response.ranked_frame
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)
    if args.exclusions_output:
        exclusion_path = Path(args.exclusions_output)
        exclusion_path.parent.mkdir(parents=True, exist_ok=True)
        if response.excluded_rows:
            import pandas as pd

            pd.DataFrame(response.excluded_rows).to_csv(exclusion_path, index=False)
        else:
            exclusion_path.write_text("ticker,reason\n", encoding="utf-8")
    if frame.empty:
        print("No securities passed the screen.")
        return
    print(frame.to_string(index=False, justify="left", float_format=lambda value: f"{value:,.6f}"))


def _run_simulate(args: argparse.Namespace) -> None:
    response = BacktestService().run(
        _build_backtest_request(args),
    )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    response.equity_curve_frame.to_csv(output_dir / "equity_curve.csv", index=False)
    response.trades_frame.to_csv(output_dir / "trades.csv", index=False)
    if response.trade_summary_frame is not None:
        response.trade_summary_frame.to_csv(output_dir / "trade_summary.csv", index=False)
    if response.review_targets_frame is not None:
        response.review_targets_frame.to_csv(output_dir / "review_targets.csv", index=False)
    response.final_holdings_frame.to_csv(output_dir / "final_holdings.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(response.summary_payload, indent=2), encoding="utf-8")
    print(json.dumps(response.summary_payload, indent=2))


def _build_screen_request(args: argparse.Namespace) -> ScreenRequest:
    return ScreenRequest(
        universe=_build_universe_request(args),
        config=ScreenConfig(
            top_n=args.top,
            momentum_mode=args.momentum_mode,
            sector_allowlist=_parse_sector_allowlist(args.sector),
            min_market_cap=args.min_market_cap,
        ),
        provider=_build_provider_config(args),
    )


def _build_backtest_request(args: argparse.Namespace) -> BacktestRequest:
    return BacktestRequest(
        universe=_build_universe_request(args),
        config=BacktestConfig(
            start_date=parse_date(args.start),
            end_date=parse_date(args.end),
            initial_capital=args.capital,
            portfolio_size=args.positions,
            benchmark=args.benchmark,
            momentum_mode=args.momentum_mode,
            sector_allowlist=_parse_sector_allowlist(args.sector),
            min_market_cap=args.min_market_cap,
        ),
        provider=_build_provider_config(args),
    )


def _add_universe_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--profile", help="Built-in universe profile")
    group.add_argument("--universe-file", help="Path to a newline-delimited ticker file")
    group.add_argument("--tickers", help="Comma-separated ticker list")


def _add_cache_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cache-ttl-hours",
        type=float,
        default=24.0,
        help="How long to reuse cached fundamentals snapshots before refreshing them",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore any existing local cache for this run and write fresh snapshots",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable the persistent local fundamentals cache for this run",
    )


def _build_universe_request(args: argparse.Namespace) -> UniverseRequest:
    if getattr(args, "profile", None):
        return UniverseRequest(profile=args.profile, candidate_limit=getattr(args, "candidate_limit", None))
    if getattr(args, "universe_file", None):
        return UniverseRequest(universe_file=args.universe_file, candidate_limit=getattr(args, "candidate_limit", None))
    return UniverseRequest(
        tickers=[ticker.strip() for ticker in args.tickers.split(",") if ticker.strip()],
        candidate_limit=getattr(args, "candidate_limit", None),
    )


def _parse_sector_allowlist(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


def _build_provider_config(args: argparse.Namespace) -> ProviderConfig:
    return ProviderConfig(
        use_cache=not args.no_cache,
        refresh_cache=args.refresh_cache,
        cache_ttl_hours=args.cache_ttl_hours,
    )


if __name__ == "__main__":
    main()
