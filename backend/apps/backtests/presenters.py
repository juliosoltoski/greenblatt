from __future__ import annotations

from apps.backtests.models import (
    BacktestEquityPoint,
    BacktestFinalHolding,
    BacktestReviewTarget,
    BacktestRun,
    BacktestTrade,
)
from apps.jobs.presenters import serialize_job
from apps.universes.presenters import serialize_universe
from apps.workspaces.presenters import serialize_workspace


def serialize_backtest_artifacts(backtest_run: BacktestRun) -> list[dict[str, object | None]]:
    artifacts: list[dict[str, object | None]] = [
        {
            "kind": "json",
            "label": "Full run JSON",
            "filename": f"backtest-run-{backtest_run.id}.json",
            "download_url": f"/api/v1/backtests/{backtest_run.id}/export/json/",
        }
    ]
    if backtest_run.has_export:
        artifacts.insert(
            0,
            {
                "kind": "zip",
                "label": "Backtest artifacts ZIP",
                "filename": backtest_run.export_filename,
                "checksum_sha256": backtest_run.export_checksum_sha256,
                "size_bytes": backtest_run.export_size_bytes,
                "download_url": f"/api/v1/backtests/{backtest_run.id}/export/",
            },
        )
    return artifacts


def serialize_backtest_equity_point(point: BacktestEquityPoint) -> dict[str, object | None]:
    return {
        "id": point.id,
        "position": point.position,
        "date": point.date.isoformat(),
        "cash": point.cash,
        "equity": point.equity,
        "positions": point.positions,
        "benchmark_equity": point.benchmark_equity,
    }


def serialize_backtest_trade(trade: BacktestTrade) -> dict[str, object | None]:
    return {
        "id": trade.id,
        "position": trade.position,
        "date": trade.date.isoformat(),
        "ticker": trade.ticker,
        "side": trade.side,
        "shares": trade.shares,
        "price": trade.price,
        "proceeds": trade.proceeds,
        "reason": trade.reason,
    }


def serialize_backtest_review_target(target: BacktestReviewTarget) -> dict[str, object | None]:
    return {
        "id": target.id,
        "position": target.position,
        "date": target.date.isoformat(),
        "target_rank": target.target_rank,
        "ticker": target.ticker,
        "company_name": target.company_name or None,
        "sector": target.sector or None,
        "industry": target.industry or None,
        "final_score": target.final_score,
        "composite_score": target.composite_score,
        "roc_rank": target.roc_rank,
        "ey_rank": target.ey_rank,
        "momentum_rank": target.momentum_rank,
    }


def serialize_backtest_final_holding(holding: BacktestFinalHolding) -> dict[str, object | None]:
    return {
        "id": holding.id,
        "position": holding.position,
        "ticker": holding.ticker,
        "shares": holding.shares,
        "entry_date": holding.entry_date.isoformat(),
        "entry_price": holding.entry_price,
        "score": holding.score,
    }


def serialize_backtest_run(backtest_run: BacktestRun) -> dict[str, object | None]:
    return {
        "id": backtest_run.id,
        "workflow_kind": "backtest",
        "workspace": serialize_workspace(backtest_run.workspace),
        "created_by_id": backtest_run.created_by_id,
        "source_template_id": backtest_run.source_template_id,
        "universe": serialize_universe(backtest_run.universe),
        "job": serialize_job(backtest_run.job),
        "start_date": backtest_run.start_date.isoformat(),
        "end_date": backtest_run.end_date.isoformat(),
        "initial_capital": backtest_run.initial_capital,
        "portfolio_size": backtest_run.portfolio_size,
        "review_frequency": backtest_run.review_frequency,
        "benchmark": backtest_run.benchmark or None,
        "momentum_mode": backtest_run.momentum_mode,
        "sector_allowlist": backtest_run.sector_allowlist,
        "min_market_cap": backtest_run.min_market_cap,
        "use_cache": backtest_run.use_cache,
        "refresh_cache": backtest_run.refresh_cache,
        "cache_ttl_hours": backtest_run.cache_ttl_hours,
        "equity_point_count": backtest_run.equity_point_count,
        "trade_count": backtest_run.trade_count,
        "review_target_count": backtest_run.review_target_count,
        "final_holding_count": backtest_run.final_holding_count,
        "summary": backtest_run.summary,
        "export": (
            {
                "storage_backend": backtest_run.export_storage_backend,
                "storage_key": backtest_run.export_storage_key,
                "filename": backtest_run.export_filename,
                "checksum_sha256": backtest_run.export_checksum_sha256,
                "size_bytes": backtest_run.export_size_bytes,
                "download_url": f"/api/v1/backtests/{backtest_run.id}/export/",
            }
            if backtest_run.has_export
            else None
        ),
        "artifacts": serialize_backtest_artifacts(backtest_run),
        "created_at": backtest_run.created_at.isoformat(),
        "updated_at": backtest_run.updated_at.isoformat(),
    }


def serialize_backtest_run_bundle(
    backtest_run: BacktestRun,
    *,
    equity_points: list[BacktestEquityPoint] | None = None,
    trades: list[BacktestTrade] | None = None,
    review_targets: list[BacktestReviewTarget] | None = None,
    final_holdings: list[BacktestFinalHolding] | None = None,
) -> dict[str, object | None]:
    return {
        "run": serialize_backtest_run(backtest_run),
        "equity_points": [serialize_backtest_equity_point(point) for point in (equity_points or list(backtest_run.equity_points.all()))],
        "trades": [serialize_backtest_trade(trade) for trade in (trades or list(backtest_run.trades.all()))],
        "review_targets": [serialize_backtest_review_target(target) for target in (review_targets or list(backtest_run.review_targets.all()))],
        "final_holdings": [serialize_backtest_final_holding(holding) for holding in (final_holdings or list(backtest_run.final_holdings.all()))],
    }
