from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date

import pandas as pd

from greenblatt.models import SecuritySnapshot


class MarketDataProvider(ABC):
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
