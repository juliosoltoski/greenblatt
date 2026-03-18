from __future__ import annotations

from dataclasses import replace
from datetime import date

import pandas as pd

from greenblatt.models import BacktestConfig, ScreenConfig, SecuritySnapshot
from greenblatt.providers.base import MarketDataProvider
from greenblatt.services import (
    BacktestRequest,
    BacktestService,
    ProviderConfig,
    ScreenRequest,
    ScreenService,
    UniverseRequest,
    UniverseService,
    frame_to_records,
    normalize_payload,
    provider_config_from_payload,
    provider_result_payload,
    serialize_provider_config,
)


class FakeProvider(MarketDataProvider):
    provider_name = "fake"
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


def make_snapshot(
    ticker: str,
    rank_seed: int = 0,
    *,
    sector: str = "Technology",
    industry: str = "Software",
    is_adr: bool = False,
    momentum_6m: float | None = None,
) -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker=ticker,
        company_name=f"{ticker} Holdings",
        sector=sector,
        industry=industry,
        is_adr=is_adr,
        market_cap=220 - rank_seed,
        ebit=50 - rank_seed,
        current_assets=60,
        current_liabilities=20,
        cash_and_equivalents=10,
        total_debt=20,
        net_pp_e=60,
        momentum_6m=momentum_6m,
    )


def test_universe_service_resolves_profile_with_candidate_limit() -> None:
    provider = FakeProvider(
        snapshots=[make_snapshot("AAA"), make_snapshot("BBB"), make_snapshot("CCC")],
        prices=pd.DataFrame(),
    )

    resolved = UniverseService().resolve(
        UniverseRequest(profile="us_top_3000", candidate_limit=2),
        provider,
    )

    assert resolved.source_type == "profile"
    assert resolved.source_value == "us_top_3000"
    assert resolved.total_candidates == 3
    assert resolved.tickers == ["AAA", "BBB"]
    assert resolved.resolved_count == 2


def test_screen_service_returns_frames_and_serialized_rows() -> None:
    provider = FakeProvider(
        snapshots=[
            make_snapshot("AAA", rank_seed=1, momentum_6m=0.10),
            make_snapshot("BBB", rank_seed=2, momentum_6m=0.25),
            make_snapshot("ADR", rank_seed=3, is_adr=True),
        ],
        prices=pd.DataFrame(),
    )

    response = ScreenService().run(
        ScreenRequest(
            universe=UniverseRequest(tickers=["AAA", "BBB", "ADR"]),
            config=ScreenConfig(top_n=5, momentum_mode="overlay"),
            provider=ProviderConfig(use_cache=False),
        ),
        provider=provider,
    )

    assert list(response.ranked_frame["ticker"]) == ["AAA", "BBB"]
    assert [row["ticker"] for row in response.ranked_rows] == ["AAA", "BBB"]
    assert response.excluded_rows == [{"ticker": "ADR", "reason": "adr excluded"}]
    assert response.resolved_universe.source_type == "tickers"
    assert response.resolved_universe.total_candidates == 3


def test_backtest_service_serializes_tabular_outputs() -> None:
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

    response = BacktestService().run(
        BacktestRequest(
            universe=UniverseRequest(tickers=["AAA", "BBB", "CCC"]),
            config=BacktestConfig(
                start_date=date(2024, 1, 5),
                end_date=date(2025, 2, 14),
                initial_capital=100_000.0,
                portfolio_size=2,
                benchmark="^GSPC",
            ),
            provider=ProviderConfig(use_cache=False),
        ),
        provider=provider,
    )

    assert response.summary_payload["ending_positions"] == 2
    assert response.equity_curve_rows[0]["date"] == "2024-01-05"
    assert response.trade_rows[0]["side"] == "BUY"
    assert response.trade_summary_rows[0]["ticker"] == "AAA"
    assert response.review_target_rows[0]["target_rank"] == 1
    assert set(row["ticker"] for row in response.final_holding_rows) == {"AAA", "CCC"}


def test_serialization_helpers_normalize_dates_and_missing_values() -> None:
    frame = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-05"),
                "value": pd.NA,
                "nested": {"when": date(2024, 1, 6)},
            }
        ]
    )

    records = frame_to_records(frame)

    assert records == [{"date": "2024-01-05T00:00:00", "value": None, "nested": {"when": "2024-01-06"}}]
    assert normalize_payload({"when": date(2024, 1, 7), "value": pd.NA}) == {
        "when": "2024-01-07",
        "value": None,
    }


def test_provider_config_payload_round_trips() -> None:
    config = provider_config_from_payload(
        {
            "provider_name": "alpha-vantage",
            "fallback_provider_name": "yahoo",
            "use_cache": False,
            "refresh_cache": True,
            "cache_ttl_hours": "12",
        }
    )

    assert serialize_provider_config(config) == {
        "provider_name": "alpha_vantage",
        "fallback_provider_name": "yahoo",
        "use_cache": False,
        "refresh_cache": True,
        "cache_ttl_hours": 12.0,
    }


def test_provider_result_payload_uses_failover_metadata() -> None:
    provider = FakeProvider(snapshots=[], prices=pd.DataFrame())
    provider.fallback_used = True  # type: ignore[attr-defined]
    provider.resolved_provider_name = "yahoo"  # type: ignore[attr-defined]

    payload = provider_result_payload(
        provider,
        ProviderConfig(provider_name="alpha_vantage", fallback_provider_name="yahoo"),
    )

    assert payload["provider_name"] == "alpha_vantage"
    assert payload["fallback_provider_name"] == "yahoo"
    assert payload["resolved_provider_name"] == "yahoo"
    assert payload["fallback_used"] is True
