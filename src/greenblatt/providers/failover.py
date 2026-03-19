from __future__ import annotations

from greenblatt.providers.base import MarketDataProvider, ProviderHealth
from greenblatt.providers.errors import is_provider_exception


class FailoverProvider(MarketDataProvider):
    provider_name = "failover"

    def __init__(self, primary: MarketDataProvider, fallback: MarketDataProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.primary_provider_name = primary.provider_name
        self.fallback_provider_name = fallback.provider_name
        self.resolved_provider_name = primary.provider_name
        self.fallback_used = False
        self.supports_historical_fundamentals = (
            primary.supports_historical_fundamentals and fallback.supports_historical_fundamentals
        )

    def get_snapshots(self, tickers, *, as_of=None, include_momentum=True):
        return self._call("get_snapshots", tickers, as_of=as_of, include_momentum=include_momentum)

    def get_price_history(self, tickers, *, start, end, interval="1d", auto_adjust=False):
        return self._call("get_price_history", tickers, start=start, end=end, interval=interval, auto_adjust=auto_adjust)

    def get_us_equity_candidates(self, *, limit: int = 3_000):
        return self._call("get_us_equity_candidates", limit=limit)

    def get_us_sector_candidates(self, *, sector: str, limit: int | None = None):
        return self._call("get_us_sector_candidates", sector=sector, limit=limit)

    def check_health(self, *, probe: bool = False) -> ProviderHealth:
        primary_health = self.primary.check_health(probe=probe)
        if primary_health.state == "ok":
            return primary_health
        fallback_health = self.fallback.check_health(probe=probe)
        if fallback_health.state == "ok":
            detail = "; ".join(
                filter(
                    None,
                    [
                        f"Primary {self.primary.provider_name}: {primary_health.detail}" if primary_health.detail else None,
                        f"Fallback {self.fallback.provider_name}: {fallback_health.detail}" if fallback_health.detail else None,
                    ],
                )
            ) or None
            return ProviderHealth(
                provider_name=self.provider_name,
                state="degraded",
                detail=detail,
                supports_historical_fundamentals=self.supports_historical_fundamentals,
            )
        detail = "; ".join(filter(None, [primary_health.detail, fallback_health.detail])) or None
        return ProviderHealth(
            provider_name=self.provider_name,
            state="error",
            detail=detail,
            supports_historical_fundamentals=self.supports_historical_fundamentals,
        )

    def _call(self, method_name: str, *args, **kwargs):
        method = getattr(self.primary, method_name)
        try:
            if not self.fallback_used:
                self.resolved_provider_name = self.primary.provider_name
            return method(*args, **kwargs)
        except Exception as exc:
            if not is_provider_exception(exc):
                raise
            self.fallback_used = True
            self.resolved_provider_name = self.fallback.provider_name
            fallback_method = getattr(self.fallback, method_name)
            return fallback_method(*args, **kwargs)
