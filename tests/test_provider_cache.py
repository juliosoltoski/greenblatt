import json

from greenblatt.models import SecuritySnapshot
from greenblatt.providers.yahoo import YahooFinanceProvider


def make_snapshot(ticker: str, *, company_name: str | None = None) -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker=ticker,
        company_name=company_name or f"{ticker} Corp",
        sector="Technology",
        industry="Software",
        market_cap=100.0,
        ebit=10.0,
        current_assets=20.0,
        current_liabilities=5.0,
        cash_and_equivalents=2.0,
        total_debt=1.0,
        net_pp_e=15.0,
    )


def test_snapshot_cache_persists_between_provider_instances(tmp_path) -> None:
    provider = YahooFinanceProvider(cache_dir=tmp_path, use_cache=True, cache_ttl_hours=24)
    fetch_calls: list[str] = []
    provider._fetch_snapshot_live = lambda ticker, as_of=None: fetch_calls.append(ticker) or make_snapshot(ticker)  # type: ignore[method-assign]

    first = provider.get_snapshots(["AAPL"], include_momentum=False)

    assert fetch_calls == ["AAPL"]
    assert first[0].company_name == "AAPL Corp"

    second_provider = YahooFinanceProvider(cache_dir=tmp_path, use_cache=True, cache_ttl_hours=24)
    second_provider._fetch_snapshot_live = lambda ticker, as_of=None: (_ for _ in ()).throw(AssertionError("cache should be used"))  # type: ignore[method-assign]

    second = second_provider.get_snapshots(["AAPL"], include_momentum=False)

    assert second[0].ticker == "AAPL"
    assert second[0].company_name == "AAPL Corp"


def test_expired_snapshot_cache_refreshes_from_live_source(tmp_path) -> None:
    provider = YahooFinanceProvider(cache_dir=tmp_path, use_cache=True, cache_ttl_hours=24)
    provider._fetch_snapshot_live = lambda ticker, as_of=None: make_snapshot(ticker, company_name="stale")  # type: ignore[method-assign]
    provider.get_snapshots(["AAPL"], include_momentum=False)

    cache_path = provider._snapshot_cache_path("AAPL")
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    payload["cached_at"] = "2000-01-01T00:00:00+00:00"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    refreshed_calls: list[str] = []
    second_provider = YahooFinanceProvider(cache_dir=tmp_path, use_cache=True, cache_ttl_hours=24)
    second_provider._fetch_snapshot_live = lambda ticker, as_of=None: refreshed_calls.append(ticker) or make_snapshot(ticker, company_name="fresh")  # type: ignore[method-assign]

    refreshed = second_provider.get_snapshots(["AAPL"], include_momentum=False)

    assert refreshed_calls == ["AAPL"]
    assert refreshed[0].company_name == "fresh"
