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
    description: str
    source: str


PROFILES: dict[str, UniverseProfile] = {
    "us_top_3000": UniverseProfile(
        key="us_top_3000",
        description="Broad U.S. listed equity universe ranked down to the top 3000 by market cap.",
        source="Nasdaq stock screener API with Nasdaq Trader fallback",
    ),
    "eu_benelux_nordic": UniverseProfile(
        key="eu_benelux_nordic",
        description="Starter Benelux and Nordic equity watchlist using Yahoo suffixes.",
        source="bundled universe file",
    ),
    "india_nifty100": UniverseProfile(
        key="india_nifty100",
        description="Starter NIFTY-style universe using Yahoo India suffixes.",
        source="bundled universe file",
    ),
    "china_hk": UniverseProfile(
        key="china_hk",
        description="Starter Shanghai, Shenzhen, and Hong Kong watchlist.",
        source="bundled universe file",
    ),
    "sector_tech": UniverseProfile(
        key="sector_tech",
        description="Starter global technology-focused list with financials and utilities still excluded.",
        source="bundled universe file",
    ),
    "sector_healthcare": UniverseProfile(
        key="sector_healthcare",
        description="Starter global healthcare-focused list with financials and utilities still excluded.",
        source="bundled universe file",
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
    if profile == "eu_benelux_nordic":
        return _load_packaged_universe("eu_benelux_nordic.txt")
    if profile == "india_nifty100":
        return _load_packaged_universe("india_nifty100.txt")
    if profile == "china_hk":
        return _load_packaged_universe("china_hk.txt")
    if profile == "sector_tech":
        return _load_packaged_universe("sector_tech.txt")
    if profile == "sector_healthcare":
        return _load_packaged_universe("sector_healthcare.txt")
    raise KeyError(f"Unknown profile: {profile}")


def load_custom_universe(path: str | Path) -> list[str]:
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
