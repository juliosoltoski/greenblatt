from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


MomentumMode = Literal["none", "overlay", "filter"]


@dataclass(slots=True)
class SecuritySnapshot:
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    exchange: str | None = None
    quote_type: str | None = None
    is_adr: bool = False
    market_cap: float | None = None
    ebit: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None
    cash_and_equivalents: float | None = None
    excess_cash: float | None = None
    total_debt: float | None = None
    minority_interest: float | None = 0.0
    preferred_stock: float | None = 0.0
    net_pp_e: float | None = None
    goodwill: float | None = 0.0
    other_intangibles: float | None = 0.0
    momentum_6m: float | None = None
    as_of: date | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class RankedSecurity(SecuritySnapshot):
    return_on_capital: float | None = None
    earnings_yield: float | None = None
    enterprise_value: float | None = None
    net_working_capital: float | None = None
    roc_rank: int | None = None
    ey_rank: int | None = None
    momentum_rank: int | None = None
    composite_score: int | None = None
    final_score: int | None = None


@dataclass(slots=True)
class ExclusionRecord:
    ticker: str
    reason: str


@dataclass(slots=True)
class ScreenConfig:
    top_n: int = 30
    momentum_mode: MomentumMode = "none"
    sector_allowlist: set[str] | None = None
    min_market_cap: float | None = None
    exclude_financials: bool = True
    exclude_utilities: bool = True
    exclude_adrs: bool = True


@dataclass(slots=True)
class ScreenResult:
    ranked: list[RankedSecurity]
    excluded: list[ExclusionRecord]


@dataclass(slots=True)
class Holding:
    ticker: str
    shares: float
    entry_date: date
    entry_price: float
    score: int | None = None


@dataclass(slots=True)
class Trade:
    date: date
    ticker: str
    side: Literal["BUY", "SELL"]
    shares: float
    price: float
    proceeds: float
    reason: str


@dataclass(slots=True)
class BacktestConfig:
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    portfolio_size: int = 20
    review_frequency: str = "W-FRI"
    benchmark: str = "^GSPC"
    momentum_mode: MomentumMode = "none"
    sector_allowlist: set[str] | None = None
    min_market_cap: float | None = None


@dataclass(slots=True)
class BacktestResult:
    equity_curve: object
    trades: object
    holdings: dict[str, Holding]
    summary: dict[str, float | int | str | None]
    review_targets: object | None = None
    trade_summary: object | None = None
