from __future__ import annotations

import io
import json
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests

from greenblatt.models import SecuritySnapshot
from greenblatt.providers.base import MarketDataProvider, ProviderHealth
from greenblatt.providers.errors import ProviderConfigurationError, ProviderRateLimitError, ProviderResponseError
from greenblatt.providers.yahoo import YahooFinanceProvider
from greenblatt.utils import RateLimiter, parse_date, retry


class AlphaVantageProvider(MarketDataProvider):
    provider_name = "alpha_vantage"
    supports_historical_fundamentals = False

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://www.alphavantage.co/query",
        max_calls_per_minute: int = 5,
        timeout_seconds: int = 30,
        cache_dir: str | Path | None = None,
        cache_ttl_hours: float = 24.0,
        use_cache: bool = True,
        refresh_cache: bool = False,
        session: requests.Session | None = None,
        candidate_provider: MarketDataProvider | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError("ALPHA_VANTAGE_API_KEY is required when provider=alpha_vantage.")

        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.rate_limiter = RateLimiter(max_calls=max_calls_per_minute, window_seconds=60)
        self.session = session or requests.Session()
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "greenblatt-magic" / "alpha_vantage"
        self.snapshot_cache_dir = self.cache_dir / "snapshots"
        if self.use_cache:
            self.snapshot_cache_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_cache: dict[str, SecuritySnapshot] = {}
        self._candidate_provider = candidate_provider

    def get_snapshots(
        self,
        tickers: list[str] | tuple[str, ...],
        *,
        as_of: date | None = None,
        include_momentum: bool = True,
    ) -> list[SecuritySnapshot]:
        universe = list(dict.fromkeys(ticker.strip().upper() for ticker in tickers if ticker and ticker.strip()))
        if not universe:
            return []

        momentum_map: dict[str, float | None] = {}
        if include_momentum:
            momentum_map = self._build_momentum_map(universe, as_of=as_of)

        snapshots: list[SecuritySnapshot] = []
        failures: dict[str, str] = {}
        for ticker in universe:
            try:
                snapshot = self._fetch_snapshot(ticker, as_of=as_of)
            except Exception as exc:
                failures[ticker] = str(exc)
                continue
            snapshot.momentum_6m = momentum_map.get(ticker)
            snapshots.append(snapshot)

        if not snapshots and failures:
            sample = "; ".join(f"{ticker}: {reason}" for ticker, reason in list(failures.items())[:3])
            raise ProviderResponseError(f"Alpha Vantage returned no usable fundamentals. Sample failures: {sample}")
        return sorted(snapshots, key=lambda snapshot: snapshot.ticker)

    def get_price_history(
        self,
        tickers: list[str] | tuple[str, ...],
        *,
        start: date | str,
        end: date | str,
        interval: str = "1d",
        auto_adjust: bool = False,
    ) -> pd.DataFrame:
        if interval != "1d":
            raise ProviderResponseError("Alpha Vantage provider currently supports daily price history only.")

        start_date = parse_date(start)
        end_date = parse_date(end)
        frames: list[pd.Series] = []
        for ticker in dict.fromkeys(ticker.strip().upper() for ticker in tickers if ticker and ticker.strip()):
            csv_text = self._request_csv_text(
                "TIME_SERIES_DAILY_ADJUSTED",
                symbol=self._provider_symbol(ticker),
                outputsize="full",
            )
            frame = pd.read_csv(io.StringIO(csv_text))
            if frame.empty or "timestamp" not in frame.columns:
                continue
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=False)
            frame = frame.sort_values("timestamp")
            frame = frame[(frame["timestamp"] >= pd.Timestamp(start_date)) & (frame["timestamp"] <= pd.Timestamp(end_date))]
            if frame.empty:
                continue
            field_name = "close" if auto_adjust else "adjusted_close"
            if field_name not in frame.columns:
                field_name = "close"
            series = pd.Series(frame[field_name].astype(float).values, index=frame["timestamp"], name=ticker)
            frames.append(series)

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=1).sort_index()

    def get_us_equity_candidates(self, *, limit: int = 3_000) -> list[str]:
        if self._candidate_provider is None:
            self._candidate_provider = YahooFinanceProvider(use_cache=False, refresh_cache=True)
        return self._candidate_provider.get_us_equity_candidates(limit=limit)

    def check_health(self, *, probe: bool = False) -> ProviderHealth:
        if not self.api_key:
            return ProviderHealth(
                provider_name=self.provider_name,
                state="unconfigured",
                detail="ALPHA_VANTAGE_API_KEY is missing.",
                supports_historical_fundamentals=self.supports_historical_fundamentals,
            )
        if not probe:
            return ProviderHealth(
                provider_name=self.provider_name,
                state="ok",
                detail="Provider is configured.",
                supports_historical_fundamentals=self.supports_historical_fundamentals,
            )
        try:
            payload = self._request_json("OVERVIEW", symbol="IBM")
            detail = "Probe request succeeded." if payload.get("Symbol") else "Probe completed without a Symbol field."
            return ProviderHealth(
                provider_name=self.provider_name,
                state="ok",
                detail=detail,
                supports_historical_fundamentals=self.supports_historical_fundamentals,
            )
        except Exception as exc:
            return ProviderHealth(
                provider_name=self.provider_name,
                state="error",
                detail=str(exc),
                supports_historical_fundamentals=self.supports_historical_fundamentals,
            )

    def _fetch_snapshot(self, ticker: str, *, as_of: date | None = None) -> SecuritySnapshot:
        if ticker in self._snapshot_cache and as_of is None:
            return self._snapshot_cache[ticker]

        if as_of is None:
            cached = self._load_cached_snapshot(ticker)
            if cached is not None:
                self._snapshot_cache[ticker] = cached
                return cached

        snapshot = self._fetch_snapshot_live(ticker, as_of=as_of)
        if as_of is None:
            self._snapshot_cache[ticker] = snapshot
            self._save_cached_snapshot(snapshot)
        return snapshot

    def _fetch_snapshot_live(self, ticker: str, *, as_of: date | None = None) -> SecuritySnapshot:
        provider_symbol = self._provider_symbol(ticker)
        overview = self._request_json("OVERVIEW", symbol=provider_symbol)
        income_statement = self._request_json("INCOME_STATEMENT", symbol=provider_symbol)
        balance_sheet = self._request_json("BALANCE_SHEET", symbol=provider_symbol)

        income_report = self._latest_report(income_statement)
        balance_report = self._latest_report(balance_sheet)

        cash_value = self._best_float(
            balance_report,
            "cashAndCashEquivalentsAtCarryingValue",
            "cashAndShortTermInvestments",
            "cashAndCashEquivalents",
        )
        total_debt = self._best_float(
            balance_report,
            "shortLongTermDebtTotal",
            "totalDebt",
        )
        if total_debt is None:
            total_debt = sum(
                value or 0.0
                for value in (
                    self._best_float(balance_report, "currentDebt", "shortTermDebt"),
                    self._best_float(balance_report, "longTermDebt", "longTermDebtNoncurrent"),
                )
            ) or None

        name = str(overview.get("Name") or ticker).strip() or ticker
        asset_type = str(overview.get("AssetType") or "").strip() or None

        return SecuritySnapshot(
            ticker=ticker,
            company_name=name,
            sector=self._clean_string(overview.get("Sector")),
            industry=self._clean_string(overview.get("Industry")),
            country=self._clean_string(overview.get("Country")),
            exchange=self._clean_string(overview.get("Exchange")),
            quote_type=asset_type,
            is_adr=asset_type == "ADR" or " ADR" in name.upper(),
            market_cap=self._best_float(overview, "MarketCapitalization"),
            ebit=self._best_float(income_report, "ebit", "operatingIncome"),
            current_assets=self._best_float(balance_report, "totalCurrentAssets"),
            current_liabilities=self._best_float(balance_report, "totalCurrentLiabilities"),
            cash_and_equivalents=cash_value,
            excess_cash=cash_value,
            total_debt=total_debt,
            minority_interest=self._best_float(balance_report, "minorityInterest") or 0.0,
            preferred_stock=self._best_float(balance_report, "preferredStock") or 0.0,
            net_pp_e=self._best_float(balance_report, "propertyPlantEquipment", "propertyPlantAndEquipmentNet"),
            goodwill=self._best_float(balance_report, "goodwill") or 0.0,
            other_intangibles=self._best_float(balance_report, "intangibleAssetsExcludingGoodwill", "otherIntangibleAssets")
            or 0.0,
            as_of=as_of or date.today(),
            metadata={
                "provider": self.provider_name,
                "currency": overview.get("Currency"),
                "description": overview.get("Description"),
            },
        )

    def _build_momentum_map(self, tickers: list[str], *, as_of: date | None = None) -> dict[str, float | None]:
        end_date = as_of or date.today()
        start_date = end_date - timedelta(days=270)
        prices = self.get_price_history(tickers, start=start_date, end=end_date)
        if prices.empty:
            return {ticker: None for ticker in tickers}

        momentum: dict[str, float | None] = {}
        for ticker in tickers:
            if ticker not in prices.columns:
                momentum[ticker] = None
                continue
            series = prices[ticker].dropna()
            if len(series) < 90:
                momentum[ticker] = None
                continue
            end_price = float(series.iloc[-1])
            anchor = series.index[-1] - pd.Timedelta(days=182)
            window = series[series.index <= anchor]
            if window.empty:
                momentum[ticker] = None
                continue
            start_price = float(window.iloc[-1])
            if start_price <= 0:
                momentum[ticker] = None
                continue
            momentum[ticker] = (end_price / start_price) - 1
        return momentum

    def _request_json(self, function: str, **params: object) -> dict[str, Any]:
        self.rate_limiter.wait()
        response = retry(
            self.session.get,
            self.base_url,
            params={"function": function, "apikey": self.api_key, **params},
            timeout=self.timeout_seconds,
            max_attempts=3,
            exceptions=(requests.RequestException,),
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ProviderResponseError(f"Alpha Vantage returned an unexpected response for {function}.")
        self._raise_for_payload_error(payload)
        return payload

    def _request_csv_text(self, function: str, **params: object) -> str:
        self.rate_limiter.wait()
        response = retry(
            self.session.get,
            self.base_url,
            params={"function": function, "apikey": self.api_key, "datatype": "csv", **params},
            timeout=self.timeout_seconds,
            max_attempts=3,
            exceptions=(requests.RequestException,),
        )
        response.raise_for_status()
        text = response.text
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            self._raise_for_payload_error(payload)
        return text

    @staticmethod
    def _raise_for_payload_error(payload: dict[str, Any]) -> None:
        if payload.get("Error Message"):
            raise ProviderResponseError(str(payload["Error Message"]))
        info = str(payload.get("Information") or payload.get("Note") or "").strip()
        if info:
            lowered = info.lower()
            if "rate" in lowered or "frequency" in lowered or "premium" in lowered:
                raise ProviderRateLimitError(info)
            raise ProviderResponseError(info)

    @staticmethod
    def _latest_report(payload: dict[str, Any]) -> dict[str, Any]:
        for key in ("annualReports", "quarterlyReports"):
            reports = payload.get(key)
            if isinstance(reports, list) and reports:
                latest = reports[0]
                if isinstance(latest, dict):
                    return latest
        return {}

    @staticmethod
    def _best_float(mapping: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = mapping.get(key)
            number = AlphaVantageProvider._as_float(value)
            if number is not None:
                return number
        return None

    def _load_cached_snapshot(self, ticker: str) -> SecuritySnapshot | None:
        if not self.use_cache or self.refresh_cache:
            return None
        path = self._snapshot_cache_path(ticker)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(payload["cached_at"])
            snapshot = self._deserialize_snapshot(payload["snapshot"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - cached_at > self.cache_ttl:
            return None
        return snapshot

    def _save_cached_snapshot(self, snapshot: SecuritySnapshot) -> None:
        if not self.use_cache:
            return
        path = self._snapshot_cache_path(snapshot.ticker)
        payload = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "snapshot": self._serialize_snapshot(snapshot),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=True, default=str), encoding="utf-8")
        temp_path.replace(path)

    def _snapshot_cache_path(self, ticker: str) -> Path:
        return self.snapshot_cache_dir / f"{quote(ticker, safe='')}.json"

    @staticmethod
    def _serialize_snapshot(snapshot: SecuritySnapshot) -> dict[str, Any]:
        payload = asdict(snapshot)
        if payload["as_of"] is not None:
            payload["as_of"] = payload["as_of"].isoformat()
        return payload

    @staticmethod
    def _deserialize_snapshot(payload: dict[str, Any]) -> SecuritySnapshot:
        data = dict(payload)
        as_of = data.get("as_of")
        if isinstance(as_of, str) and as_of:
            data["as_of"] = date.fromisoformat(as_of)
        else:
            data["as_of"] = None
        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            data["metadata"] = {}
        return SecuritySnapshot(**data)

    @staticmethod
    def _provider_symbol(ticker: str) -> str:
        normalized = ticker.strip().upper()
        if "." in normalized or normalized.startswith("^") or "=" in normalized:
            return normalized
        if "-" in normalized:
            base, suffix = normalized.rsplit("-", 1)
            if len(suffix) == 1 and suffix.isalpha():
                return f"{base}.{suffix}"
        return normalized

    @staticmethod
    def _clean_string(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
