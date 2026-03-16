from dataclasses import replace
from datetime import date

import pandas as pd

from greenblatt.models import BacktestConfig, SecuritySnapshot
from greenblatt.providers.base import MarketDataProvider
from greenblatt.simulation import MagicFormulaBacktester


class FakeProvider(MarketDataProvider):
    supports_historical_fundamentals = False

    def __init__(self, snapshots: list[SecuritySnapshot], prices: pd.DataFrame) -> None:
        self.snapshots = snapshots
        self.prices = prices

    def get_snapshots(self, tickers, *, as_of=None, include_momentum=True):
        lookup = {snapshot.ticker: snapshot for snapshot in self.snapshots}
        return [replace(lookup[ticker]) for ticker in tickers if ticker in lookup]

    def get_price_history(self, tickers, *, start, end, interval="1d", auto_adjust=False):
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)
        columns = [ticker for ticker in tickers if ticker in self.prices.columns]
        frame = self.prices.loc[(self.prices.index >= start) & (self.prices.index <= end), columns]
        return frame.copy()

    def get_us_equity_candidates(self, *, limit: int = 3_000):
        return [snapshot.ticker for snapshot in self.snapshots][:limit]


def make_snapshot(ticker: str, rank_seed: int) -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker=ticker,
        company_name=ticker,
        sector="Technology",
        industry="Software",
        market_cap=200 - rank_seed,
        ebit=60 - rank_seed,
        current_assets=80,
        current_liabilities=20,
        cash_and_equivalents=10,
        total_debt=20,
        net_pp_e=60,
    )


def test_backtester_applies_51_53_week_tax_rules_and_replaces_positions() -> None:
    dates = pd.date_range("2024-01-05", "2025-02-14", freq="W-FRI")
    prices = pd.DataFrame(
        {
            "AAA": [100.0] * 51 + [90.0] * (len(dates) - 51),
            "BBB": [100.0] * 53 + [120.0] * (len(dates) - 53),
            "CCC": [100.0] * len(dates),
            "^GSPC": [100.0 + idx for idx, _ in enumerate(dates)],
        },
        index=dates,
    )

    provider = FakeProvider(
        snapshots=[make_snapshot("AAA", 1), make_snapshot("BBB", 2), make_snapshot("CCC", 3)],
        prices=prices,
    )
    backtester = MagicFormulaBacktester(provider)

    result = backtester.run(
        ["AAA", "BBB", "CCC"],
        BacktestConfig(
            start_date=date(2024, 1, 5),
            end_date=date(2025, 2, 14),
            initial_capital=100_000.0,
            portfolio_size=2,
            benchmark="^GSPC",
        ),
    )

    trades = result.trades
    assert list(trades["side"]) == ["BUY", "BUY", "SELL", "BUY", "SELL", "BUY"]
    assert list(trades["ticker"]) == ["AAA", "BBB", "AAA", "CCC", "BBB", "AAA"]
    assert list(trades["reason"]) == [
        "initial allocation",
        "initial allocation",
        "51-week loser harvest",
        "rebalance replacement",
        "53-week winner realization",
        "rebalance replacement",
    ]
    assert trades.iloc[2]["date"].isoformat() == "2024-12-27"
    assert trades.iloc[4]["date"].isoformat() == "2025-01-10"
    assert set(result.holdings) == {"AAA", "CCC"}
    assert result.summary["ending_positions"] == 2
    assert "benchmark_return" in result.summary

    trade_summary = result.trade_summary
    assert list(trade_summary["ticker"]) == ["AAA", "BBB", "CCC"]
    assert list(trade_summary["currently_held"]) == [True, False, True]
    assert list(trade_summary["buy_count"]) == [2, 1, 1]

    review_targets = result.review_targets
    assert not review_targets.empty
    assert set(review_targets["ticker"]) == {"AAA", "BBB"}
    assert list(review_targets["target_rank"].unique()) == [1, 2]
