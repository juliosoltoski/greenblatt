from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd

from greenblatt.models import SecuritySnapshot


ProviderHealthState = Literal["ok", "degraded", "error", "unconfigured", "unknown"]


@dataclass(slots=True)
class ProviderHealth:
    provider_name: str
    state: ProviderHealthState
    detail: str | None = None
    supports_historical_fundamentals: bool = False


class MarketDataProvider(ABC):
    provider_name: str = "unknown"
    supports_historical_fundamentals: bool = False

    @abstractmethod
    def get_snapshots(
        self,
        tickers: Sequence[str],
        *,
        as_of: date | None = None,
        include_momentum: bool = True,
    ) -> list[SecuritySnapshot]:
        raise NotImplementedError

    @abstractmethod
    def get_price_history(
        self,
        tickers: Sequence[str],
        *,
        start: date | str,
        end: date | str,
        interval: str = "1d",
        auto_adjust: bool = False,
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def get_us_equity_candidates(self, *, limit: int = 3_000) -> list[str]:
        raise NotImplementedError

    def get_us_sector_candidates(self, *, sector: str, limit: int | None = None) -> list[str]:
        raise NotImplementedError(f"{self.provider_name} does not support sector-based universe candidates.")

    def check_health(self, *, probe: bool = False) -> ProviderHealth:
        state: ProviderHealthState = "unknown" if probe else "ok"
        detail = "Remote probe not implemented." if probe else None
        return ProviderHealth(
            provider_name=self.provider_name,
            state=state,
            detail=detail,
            supports_historical_fundamentals=self.supports_historical_fundamentals,
        )
