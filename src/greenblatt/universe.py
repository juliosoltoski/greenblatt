from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from greenblatt.providers.base import MarketDataProvider


@dataclass(frozen=True, slots=True)
class UniverseProfile:
    key: str
    label: str
    description: str
    source: str
    estimated_entry_count: int | None = None
    resolution_note: str | None = None
    requires_live_data: bool = False


SECTOR_PROFILE_LIMIT = 500

PACKAGED_PROFILE_FILES: dict[str, str] = {
    "eu_benelux_nordic": "eu_benelux_nordic.txt",
    "india_nifty100": "india_nifty100.txt",
    "china_hk": "china_hk.txt",
    "uk_ftse100": "uk_ftse100.txt",
    "australia_asx200": "australia_asx200.txt",
    "canada_tsx_composite": "canada_tsx_composite.txt",
}

NASDAQ_SECTOR_PROFILE_FILTERS: dict[str, str] = {
    "sector_tech": "Technology",
    "sector_healthcare": "Health Care",
    "sector_industrials": "Industrials",
    "sector_consumer_discretionary": "Consumer Discretionary",
    "sector_consumer_staples": "Consumer Staples",
    "sector_energy": "Energy",
    "sector_basic_materials": "Basic Materials",
    "sector_real_estate": "Real Estate",
    "sector_telecommunications": "Telecommunications",
}


PROFILES: dict[str, UniverseProfile] = {
    "us_top_3000": UniverseProfile(
        key="us_top_3000",
        label="US Top 3000",
        description="Broad U.S. listed equity universe ranked to the top 3,000 by market cap.",
        source="Nasdaq stock screener API with Nasdaq Trader fallback",
        estimated_entry_count=3_000,
        resolution_note="Resolved from live market data when the universe is created or synced.",
        requires_live_data=True,
    ),
    "eu_benelux_nordic": UniverseProfile(
        key="eu_benelux_nordic",
        label="Benelux & Nordic Leaders",
        description="Balanced Benelux and Nordic local-listing universe across six markets.",
        source="CompaniesMarketCap local listing pages, packaged with the app",
    ),
    "india_nifty100": UniverseProfile(
        key="india_nifty100",
        label="India Nifty 100",
        description="Nifty 100 large-cap India universe using Yahoo NSE suffixes.",
        source="Nifty 50 and NIFTY Next 50 constituent lists, packaged with the app",
    ),
    "china_hk": UniverseProfile(
        key="china_hk",
        label="China & Hong Kong Leaders",
        description="Balanced mainland China and Hong Kong local-listing universe.",
        source="CompaniesMarketCap China and Hong Kong pages, packaged with the app",
    ),
    "uk_ftse100": UniverseProfile(
        key="uk_ftse100",
        label="United Kingdom FTSE 100",
        description="FTSE 100 constituents using Yahoo London suffixes.",
        source="Wikipedia FTSE 100 constituent table, packaged with the app",
    ),
    "australia_asx200": UniverseProfile(
        key="australia_asx200",
        label="Australia ASX 200",
        description="S&P/ASX 200 constituents using Yahoo Australia suffixes.",
        source="Wikipedia S&P/ASX 200 constituent table, packaged with the app",
    ),
    "canada_tsx_composite": UniverseProfile(
        key="canada_tsx_composite",
        label="Canada TSX Composite",
        description="S&P/TSX Composite constituents using Yahoo Toronto suffixes.",
        source="Wikipedia S&P/TSX Composite constituent table, packaged with the app",
    ),
    "sector_tech": UniverseProfile(
        key="sector_tech",
        label="US Technology Leaders",
        description="Top U.S. technology equities ranked by market cap from live Nasdaq sector data.",
        source="Nasdaq stock screener API sector classification",
        resolution_note="Resolved from live market data when the universe is created or synced. Capped at 500 names.",
        requires_live_data=True,
    ),
    "sector_healthcare": UniverseProfile(
        key="sector_healthcare",
        label="US Health Care Leaders",
        description="Top U.S. health care equities ranked by market cap from live Nasdaq sector data.",
        source="Nasdaq stock screener API sector classification",
        resolution_note="Resolved from live market data when the universe is created or synced. Capped at 500 names.",
        requires_live_data=True,
    ),
    "sector_industrials": UniverseProfile(
        key="sector_industrials",
        label="US Industrials Leaders",
        description="Top U.S. industrial equities ranked by market cap from live Nasdaq sector data.",
        source="Nasdaq stock screener API sector classification",
        resolution_note="Resolved from live market data when the universe is created or synced. Capped at 500 names.",
        requires_live_data=True,
    ),
    "sector_consumer_discretionary": UniverseProfile(
        key="sector_consumer_discretionary",
        label="US Consumer Discretionary Leaders",
        description="Top U.S. consumer discretionary equities ranked by market cap from live Nasdaq sector data.",
        source="Nasdaq stock screener API sector classification",
        resolution_note="Resolved from live market data when the universe is created or synced. Capped at 500 names.",
        requires_live_data=True,
    ),
    "sector_consumer_staples": UniverseProfile(
        key="sector_consumer_staples",
        label="US Consumer Staples Leaders",
        description="Top U.S. consumer staples equities ranked by market cap from live Nasdaq sector data.",
        source="Nasdaq stock screener API sector classification",
        resolution_note="Resolved from live market data when the universe is created or synced. Capped at 500 names.",
        requires_live_data=True,
    ),
    "sector_energy": UniverseProfile(
        key="sector_energy",
        label="US Energy Leaders",
        description="Top U.S. energy equities ranked by market cap from live Nasdaq sector data.",
        source="Nasdaq stock screener API sector classification",
        resolution_note="Resolved from live market data when the universe is created or synced. Capped at 500 names.",
        requires_live_data=True,
    ),
    "sector_basic_materials": UniverseProfile(
        key="sector_basic_materials",
        label="US Basic Materials Leaders",
        description="Top U.S. basic materials equities ranked by market cap from live Nasdaq sector data.",
        source="Nasdaq stock screener API sector classification",
        resolution_note="Resolved from live market data when the universe is created or synced. Capped at 500 names.",
        requires_live_data=True,
    ),
    "sector_real_estate": UniverseProfile(
        key="sector_real_estate",
        label="US Real Estate Leaders",
        description="Top U.S. real estate equities ranked by market cap from live Nasdaq sector data.",
        source="Nasdaq stock screener API sector classification",
        resolution_note="Resolved from live market data when the universe is created or synced. Capped at 500 names.",
        requires_live_data=True,
    ),
    "sector_telecommunications": UniverseProfile(
        key="sector_telecommunications",
        label="US Telecommunications Leaders",
        description="Top U.S. telecommunications equities ranked by market cap from live Nasdaq sector data.",
        source="Nasdaq stock screener API sector classification",
        resolution_note="Resolved from live market data when the universe is created or synced. Capped at 500 names.",
        requires_live_data=True,
    ),
}


def _load_packaged_universe(filename: str) -> list[str]:
    base = resources.files("greenblatt.data.universes")
    path = base.joinpath(filename)
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def list_profiles() -> list[UniverseProfile]:
    return list(PROFILES.values())


def resolve_profile(provider: MarketDataProvider, profile: str) -> list[str]:
    if profile == "us_top_3000":
        return provider.get_us_equity_candidates(limit=3_000)
    if profile in PACKAGED_PROFILE_FILES:
        return _load_packaged_universe(PACKAGED_PROFILE_FILES[profile])
    if profile in NASDAQ_SECTOR_PROFILE_FILTERS:
        return provider.get_us_sector_candidates(
            sector=NASDAQ_SECTOR_PROFILE_FILTERS[profile],
            limit=SECTOR_PROFILE_LIMIT,
        )
    raise KeyError(f"Unknown profile: {profile}")


def load_custom_universe(path: str | Path) -> list[str]:
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
