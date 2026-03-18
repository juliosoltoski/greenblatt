from __future__ import annotations

import argparse
from datetime import date

import pandas as pd

from greenblatt.cli import _build_backtest_request, _build_screen_request, _run_providers, _run_screen
from greenblatt.models import BacktestResult, ScreenResult
from greenblatt.services import BacktestResponse, ResolvedUniverse, ScreenResponse


def test_build_screen_request_translates_args() -> None:
    args = argparse.Namespace(
        profile="us_top_3000",
        universe_file=None,
        tickers=None,
        top=25,
        candidate_limit=250,
        momentum_mode="overlay",
        sector="Technology,Healthcare",
        min_market_cap=10_000_000_000.0,
        cache_ttl_hours=48.0,
        refresh_cache=True,
        no_cache=False,
        provider="alpha_vantage",
        fallback_provider="yahoo",
    )

    request = _build_screen_request(args)

    assert request.universe.profile == "us_top_3000"
    assert request.universe.candidate_limit == 250
    assert request.config.top_n == 25
    assert request.config.momentum_mode == "overlay"
    assert request.config.sector_allowlist == {"Technology", "Healthcare"}
    assert request.provider.cache_ttl_hours == 48.0
    assert request.provider.refresh_cache is True
    assert request.provider.provider_name == "alpha_vantage"
    assert request.provider.fallback_provider_name == "yahoo"


def test_build_backtest_request_translates_args() -> None:
    args = argparse.Namespace(
        profile=None,
        universe_file="watchlist.txt",
        tickers=None,
        start="2024-01-01",
        end="2025-12-31",
        capital=250_000.0,
        positions=12,
        candidate_limit=100,
        momentum_mode="filter",
        sector="Technology",
        min_market_cap=5_000_000_000.0,
        benchmark="QQQ",
        cache_ttl_hours=24.0,
        refresh_cache=False,
        no_cache=True,
        provider="yahoo",
        fallback_provider=None,
    )

    request = _build_backtest_request(args)

    assert request.universe.universe_file == "watchlist.txt"
    assert request.universe.candidate_limit == 100
    assert request.config.start_date == date(2024, 1, 1)
    assert request.config.end_date == date(2025, 12, 31)
    assert request.config.initial_capital == 250_000.0
    assert request.config.portfolio_size == 12
    assert request.config.momentum_mode == "filter"
    assert request.config.sector_allowlist == {"Technology"}
    assert request.provider.use_cache is False
    assert request.provider.provider_name == "yahoo"


def test_run_screen_uses_screen_service(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    class FakeScreenService:
        def run(self, request):
            captured["request"] = request
            return ScreenResponse(
                request=request,
                resolved_universe=ResolvedUniverse(
                    source_type="profile",
                    source_value="us_top_3000",
                    tickers=["AAA"],
                    total_candidates=1,
                    candidate_limit=None,
                ),
                result=ScreenResult(ranked=[], excluded=[]),
                ranked_frame=pd.DataFrame(
                    [
                        {
                            "ticker": "AAA",
                            "company_name": "AAA Holdings",
                            "sector": "Technology",
                            "industry": "Software",
                            "market_cap": 100.0,
                            "ebit": 10.0,
                            "net_working_capital": 40.0,
                            "enterprise_value": 120.0,
                            "return_on_capital": 0.2,
                            "earnings_yield": 0.08,
                            "momentum_6m": None,
                            "roc_rank": 1,
                            "ey_rank": 1,
                            "momentum_rank": None,
                            "composite_score": 2,
                            "final_score": 2,
                        }
                    ]
                ),
                ranked_rows=[{"ticker": "AAA"}],
                excluded_rows=[],
            )

    monkeypatch.setattr("greenblatt.cli.ScreenService", lambda: FakeScreenService())

    args = argparse.Namespace(
        profile="us_top_3000",
        universe_file=None,
        tickers=None,
        top=10,
        candidate_limit=None,
        momentum_mode="none",
        sector=None,
        min_market_cap=None,
        cache_ttl_hours=24.0,
        refresh_cache=False,
        no_cache=False,
        provider="yahoo",
        fallback_provider=None,
        output=None,
        exclusions_output=None,
    )

    _run_screen(args)
    output = capsys.readouterr().out

    assert captured["request"].universe.profile == "us_top_3000"
    assert "AAA" in output


def test_run_providers_lists_descriptors(capsys) -> None:
    _run_providers(argparse.Namespace())

    output = capsys.readouterr().out

    assert "yahoo:" in output
    assert "alpha_vantage:" in output
