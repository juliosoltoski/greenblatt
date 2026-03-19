from __future__ import annotations

from datetime import date


def build_screen_data_quality_payload(
    *,
    resolved_count: int,
    result_count: int,
    exclusion_count: int,
    top_n: int,
    fallback_used: bool,
) -> dict[str, object]:
    warnings: list[dict[str, str]] = []
    coverage_ratio = (result_count / resolved_count) if resolved_count > 0 else 0.0
    exclusion_ratio = (exclusion_count / resolved_count) if resolved_count > 0 else 0.0

    if fallback_used:
        warnings.append(
            {
                "code": "fallback_provider_used",
                "severity": "warning",
                "message": "The fallback provider supplied this screen run after the primary provider failed.",
            }
        )
    if resolved_count >= max(top_n * 5, 50) and coverage_ratio < 0.2:
        warnings.append(
            {
                "code": "low_result_coverage",
                "severity": "warning",
                "message": "The ranked result set covers only a small fraction of the resolved universe.",
            }
        )
    if exclusion_ratio >= 0.5:
        warnings.append(
            {
                "code": "high_exclusion_ratio",
                "severity": "notice",
                "message": "A large share of resolved tickers were excluded before ranking completed.",
            }
        )
    if result_count < min(top_n, 10):
        warnings.append(
            {
                "code": "thin_result_set",
                "severity": "warning",
                "message": "The final shortlist is smaller than a typical top-ranked screen output.",
            }
        )

    return {
        "coverage_ratio": round(coverage_ratio, 4),
        "exclusion_ratio": round(exclusion_ratio, 4),
        "warning_count": len(warnings),
        "severity": _highest_severity(warnings),
        "warnings": warnings,
    }


def build_backtest_data_quality_payload(
    *,
    start_date: date,
    end_date: date,
    equity_point_count: int,
    trade_count: int,
    review_target_count: int,
    final_holding_count: int,
    fallback_used: bool,
) -> dict[str, object]:
    warnings: list[dict[str, str]] = []
    day_span = max(1, (end_date - start_date).days)
    equity_density = equity_point_count / day_span

    if fallback_used:
        warnings.append(
            {
                "code": "fallback_provider_used",
                "severity": "warning",
                "message": "The fallback provider supplied this backtest after the primary provider failed.",
            }
        )
    if equity_point_count < 20 or equity_density < 0.2:
        warnings.append(
            {
                "code": "thin_price_history",
                "severity": "warning",
                "message": "The persisted equity curve is sparse relative to the requested backtest window.",
            }
        )
    if trade_count == 0 and review_target_count == 0:
        warnings.append(
            {
                "code": "no_portfolio_turnover",
                "severity": "notice",
                "message": "The run completed without persisting review targets or trades.",
            }
        )
    if final_holding_count == 0 and equity_point_count > 0:
        warnings.append(
            {
                "code": "empty_final_holdings",
                "severity": "notice",
                "message": "The backtest finished with no final holdings to inspect.",
            }
        )

    return {
        "equity_density": round(equity_density, 4),
        "warning_count": len(warnings),
        "severity": _highest_severity(warnings),
        "warnings": warnings,
    }


def _highest_severity(warnings: list[dict[str, str]]) -> str:
    levels = [warning.get("severity") for warning in warnings]
    if "warning" in levels:
        return "warning"
    if "notice" in levels:
        return "notice"
    return "ok"
