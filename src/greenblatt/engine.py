from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

import pandas as pd

from greenblatt.models import ExclusionRecord, RankedSecurity, ScreenConfig, ScreenResult, SecuritySnapshot


FINANCIAL_KEYWORDS = (
    "bank",
    "insurance",
    "financial",
    "capital markets",
    "asset management",
    "consumer finance",
    "reit",
)

UTILITY_KEYWORDS = ("utility", "utilities", "independent power", "regulated electric")


def compute_net_working_capital(snapshot: SecuritySnapshot) -> float | None:
    if snapshot.current_assets is None or snapshot.current_liabilities is None:
        return None
    return snapshot.current_assets - snapshot.current_liabilities


def compute_enterprise_value(snapshot: SecuritySnapshot) -> float | None:
    if snapshot.market_cap is None:
        return None
    debt = snapshot.total_debt or 0.0
    minority_interest = snapshot.minority_interest or 0.0
    preferred_stock = snapshot.preferred_stock or 0.0
    excess_cash = snapshot.excess_cash
    if excess_cash is None:
        excess_cash = snapshot.cash_and_equivalents or 0.0
    enterprise_value = snapshot.market_cap + debt + minority_interest + preferred_stock - excess_cash
    if enterprise_value <= 0:
        return None
    return enterprise_value


def compute_return_on_capital(snapshot: SecuritySnapshot) -> tuple[float | None, float | None]:
    if snapshot.ebit is None:
        return None, None
    net_working_capital = compute_net_working_capital(snapshot)
    if net_working_capital is None or snapshot.net_pp_e is None:
        return None, net_working_capital
    capital_base = net_working_capital + snapshot.net_pp_e
    if capital_base <= 0:
        return None, net_working_capital
    return snapshot.ebit / capital_base, net_working_capital


def compute_earnings_yield(snapshot: SecuritySnapshot) -> tuple[float | None, float | None]:
    if snapshot.ebit is None:
        return None, None
    enterprise_value = compute_enterprise_value(snapshot)
    if enterprise_value is None:
        return None, None
    return snapshot.ebit / enterprise_value, enterprise_value


def should_exclude(snapshot: SecuritySnapshot, config: ScreenConfig) -> str | None:
    if config.min_market_cap and (snapshot.market_cap or 0) < config.min_market_cap:
        return f"market cap below minimum ({config.min_market_cap:,.0f})"

    sector = (snapshot.sector or "").lower()
    industry = (snapshot.industry or "").lower()
    name = (snapshot.company_name or "").lower()

    if config.exclude_adrs and snapshot.is_adr:
        return "adr excluded"

    if config.exclude_financials and any(keyword in sector or keyword in industry for keyword in FINANCIAL_KEYWORDS):
        return "financial institution excluded"

    if config.exclude_utilities and any(keyword in sector or keyword in industry for keyword in UTILITY_KEYWORDS):
        return "utility excluded"

    if config.sector_allowlist:
        allowed = {entry.lower() for entry in config.sector_allowlist}
        if sector not in allowed:
            return f"sector not in allowlist ({', '.join(sorted(config.sector_allowlist))})"

    if "adr" in name and config.exclude_adrs:
        return "adr excluded"
    return None


class MagicFormulaEngine:
    def __init__(self, config: ScreenConfig | None = None) -> None:
        self.config = config or ScreenConfig()

    def screen(self, snapshots: Iterable[SecuritySnapshot], config: ScreenConfig | None = None) -> ScreenResult:
        active_config = config or self.config
        ranked_rows: list[RankedSecurity] = []
        excluded: list[ExclusionRecord] = []

        for snapshot in snapshots:
            reason = should_exclude(snapshot, active_config)
            if reason:
                excluded.append(ExclusionRecord(ticker=snapshot.ticker, reason=reason))
                continue

            return_on_capital, net_working_capital = compute_return_on_capital(snapshot)
            earnings_yield, enterprise_value = compute_earnings_yield(snapshot)
            if return_on_capital is None:
                excluded.append(ExclusionRecord(ticker=snapshot.ticker, reason="insufficient data for ROC"))
                continue
            if earnings_yield is None:
                excluded.append(ExclusionRecord(ticker=snapshot.ticker, reason="insufficient data for EY"))
                continue

            ranked_rows.append(
                RankedSecurity(
                    **asdict(snapshot),
                    return_on_capital=return_on_capital,
                    earnings_yield=earnings_yield,
                    enterprise_value=enterprise_value,
                    net_working_capital=net_working_capital,
                )
            )

        if not ranked_rows:
            return ScreenResult(ranked=[], excluded=excluded)

        frame = pd.DataFrame(
            {
                "ticker": [row.ticker for row in ranked_rows],
                "roc": [row.return_on_capital for row in ranked_rows],
                "ey": [row.earnings_yield for row in ranked_rows],
                "momentum": [row.momentum_6m for row in ranked_rows],
            }
        )
        frame["roc_rank"] = frame["roc"].rank(method="min", ascending=False).astype(int)
        frame["ey_rank"] = frame["ey"].rank(method="min", ascending=False).astype(int)
        frame["composite_score"] = frame["roc_rank"] + frame["ey_rank"]

        momentum_mode = active_config.momentum_mode
        if momentum_mode != "none":
            frame["momentum_filled"] = frame["momentum"].fillna(float("-inf"))
            frame["momentum_rank"] = frame["momentum_filled"].rank(method="min", ascending=False).astype(int)
            if momentum_mode == "overlay":
                frame["final_score"] = frame["composite_score"] + frame["momentum_rank"]
            else:
                threshold = max(1, len(frame) // 2)
                frame = frame[frame["momentum_rank"] <= threshold].copy()
                frame["final_score"] = frame["composite_score"]
        else:
            frame["momentum_rank"] = pd.NA
            frame["final_score"] = frame["composite_score"]

        frame = frame.sort_values(
            by=["final_score", "composite_score", "roc_rank", "ey_rank", "ticker"],
            ascending=[True, True, True, True, True],
        ).reset_index(drop=True)
        frame = frame.head(active_config.top_n)

        ranked_lookup = {row.ticker: row for row in ranked_rows}
        ranked_output: list[RankedSecurity] = []
        for _, item in frame.iterrows():
            security = ranked_lookup[item["ticker"]]
            security.roc_rank = int(item["roc_rank"])
            security.ey_rank = int(item["ey_rank"])
            security.composite_score = int(item["composite_score"])
            security.final_score = int(item["final_score"])
            if pd.notna(item["momentum_rank"]):
                security.momentum_rank = int(item["momentum_rank"])
            ranked_output.append(security)

        included = {row.ticker for row in ranked_output}
        if momentum_mode == "filter":
            for row in ranked_rows:
                if row.ticker not in included:
                    excluded.append(ExclusionRecord(ticker=row.ticker, reason="filtered by momentum overlay"))

        return ScreenResult(ranked=ranked_output, excluded=sorted(excluded, key=lambda entry: entry.ticker))

    @staticmethod
    def to_frame(result: ScreenResult) -> pd.DataFrame:
        rows = []
        for security in result.ranked:
            rows.append(
                {
                    "ticker": security.ticker,
                    "company_name": security.company_name,
                    "sector": security.sector,
                    "industry": security.industry,
                    "market_cap": security.market_cap,
                    "ebit": security.ebit,
                    "net_working_capital": security.net_working_capital,
                    "enterprise_value": security.enterprise_value,
                    "return_on_capital": security.return_on_capital,
                    "earnings_yield": security.earnings_yield,
                    "momentum_6m": security.momentum_6m,
                    "roc_rank": security.roc_rank,
                    "ey_rank": security.ey_rank,
                    "momentum_rank": security.momentum_rank,
                    "composite_score": security.composite_score,
                    "final_score": security.final_score,
                }
            )
        return pd.DataFrame(rows)
