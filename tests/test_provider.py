from dataclasses import replace

import pandas as pd

from greenblatt.models import SecuritySnapshot
from greenblatt.providers.alpha_vantage import AlphaVantageProvider
from greenblatt.providers.errors import ProviderResponseError
from greenblatt.providers.failover import FailoverProvider
from greenblatt.providers.yahoo import YahooFinanceProvider


class _PrimaryFailureProvider:
    provider_name = "primary"
    supports_historical_fundamentals = False

    def get_snapshots(self, tickers, *, as_of=None, include_momentum=True):
        raise ProviderResponseError("primary unavailable")

    def get_price_history(self, tickers, *, start, end, interval="1d", auto_adjust=False):
        raise ProviderResponseError("primary unavailable")

    def get_us_equity_candidates(self, *, limit: int = 3_000):
        raise ProviderResponseError("primary unavailable")


class _FallbackProvider:
    provider_name = "fallback"
    supports_historical_fundamentals = False

    def __init__(self) -> None:
        self.snapshots = [
            SecuritySnapshot(
                ticker="AAPL",
                company_name="Apple",
                sector="Technology",
                industry="Hardware",
                market_cap=1.0,
                ebit=1.0,
                current_assets=1.0,
                current_liabilities=1.0,
                cash_and_equivalents=1.0,
                total_debt=1.0,
                net_pp_e=1.0,
            )
        ]

    def get_snapshots(self, tickers, *, as_of=None, include_momentum=True):
        lookup = {snapshot.ticker: snapshot for snapshot in self.snapshots}
        return [replace(lookup[ticker]) for ticker in tickers if ticker in lookup]

    def get_price_history(self, tickers, *, start, end, interval="1d", auto_adjust=False):
        return pd.DataFrame({"AAPL": [100.0]}, index=pd.date_range("2024-01-01", periods=1))

    def get_us_equity_candidates(self, *, limit: int = 3_000):
        return ["AAPL"][:limit]

def test_rank_nasdaq_stock_rows_filters_non_equities_and_sorts_by_market_cap() -> None:
    rows = [
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "marketCap": "500000000000.00"},
        {"symbol": "AAPL", "name": "Apple Inc. Common Stock", "marketCap": "3700000000000.00"},
        {"symbol": "BRK.A", "name": "Berkshire Hathaway Inc. Class A Common Stock", "marketCap": "1000000000000.00"},
        {"symbol": "XYZW", "name": "Example Holdings Warrant", "marketCap": "9000000000.00"},
        {"symbol": "MSFT", "name": "Microsoft Corporation Common Stock", "marketCap": "2900000000000.00"},
        {"symbol": "ABC", "name": "Example Depositary Shares", "marketCap": "8000000000.00"},
    ]

    ranked = YahooFinanceProvider._rank_nasdaq_stock_rows(rows)

    assert ranked[:3] == ["AAPL", "MSFT", "BRK-A"]
    assert "SPY" not in ranked
    assert "XYZW" not in ranked
    assert "ABC" not in ranked


def test_parse_pipe_delimited_rows_skips_file_creation_footer() -> None:
    text = "\n".join(
        [
            "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol",
            "AAPL|Apple Inc. Common Stock|Q|AAPL|N|100|N|AAPL",
            "File Creation Time: 0313202611:01||||||",
        ]
    )

    rows = YahooFinanceProvider._parse_pipe_delimited_rows(text)

    assert rows == [
        {
            "ACT Symbol": "AAPL",
            "Security Name": "Apple Inc. Common Stock",
            "Exchange": "Q",
            "CQS Symbol": "AAPL",
            "ETF": "N",
            "Round Lot Size": "100",
            "Test Issue": "N",
            "NASDAQ Symbol": "AAPL",
        }
    ]


def test_normalize_symbol_preserves_exchange_suffixes_and_converts_us_class_shares() -> None:
    provider = YahooFinanceProvider(use_cache=False)

    assert provider._normalize_symbol("ASML.AS") == "ASML.AS"
    assert provider._normalize_symbol("600519.SS") == "600519.SS"
    assert provider._normalize_symbol("NOVO-B.CO") == "NOVO-B.CO"
    assert provider._normalize_symbol("BRK.B") == "BRK-B"
    assert provider._normalize_symbol("BF.B") == "BF-B"


def test_alpha_vantage_provider_symbol_converts_class_shares() -> None:
    assert AlphaVantageProvider._provider_symbol("BRK-B") == "BRK.B"
    assert AlphaVantageProvider._provider_symbol("BF-B") == "BF.B"
    assert AlphaVantageProvider._provider_symbol("ASML.AS") == "ASML.AS"


def test_failover_provider_uses_fallback_on_provider_error() -> None:
    provider = FailoverProvider(_PrimaryFailureProvider(), _FallbackProvider())

    snapshots = provider.get_snapshots(["AAPL"], include_momentum=False)

    assert [snapshot.ticker for snapshot in snapshots] == ["AAPL"]
    assert provider.fallback_used is True
    assert provider.resolved_provider_name == "fallback"
