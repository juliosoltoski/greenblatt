from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import yfinance as yf
from curl_cffi import requests as curl_requests
from yfinance.exceptions import YFRateLimitError

from greenblatt.models import SecuritySnapshot
from greenblatt.providers.base import MarketDataProvider
from greenblatt.utils import RateLimiter, RetryError, parse_date, retry


FINANCIAL_ROW_ALIASES = {
    "ebit": ["EBIT", "Operating Income", "OperatingIncome", "Normalized EBIT"],
}

BALANCE_ROW_ALIASES = {
    "current_assets": ["Current Assets", "CurrentAssets"],
    "current_liabilities": ["Current Liabilities", "CurrentLiabilities"],
    "cash_and_equivalents": [
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
        "Cash And Short Term Investments",
        "CashAndCashEquivalents",
    ],
    "total_debt": ["Total Debt", "TotalDebt"],
    "minority_interest": ["Minority Interest", "MinorityInterest"],
    "preferred_stock": ["Preferred Stock", "PreferredStock"],
    "net_pp_e": [
        "Net PPE",
        "Net Property Plant Equipment",
        "Property Plant Equipment Net",
        "PropertyPlantEquipmentNet",
    ],
    "goodwill": ["Goodwill", "GoodWill"],
    "other_intangibles": ["Other Intangible Assets", "OtherIntangibleAssets"],
}

NASDAQ_STOCK_SCREENER_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&download=true"
NASDAQ_DIRECTORY_URLS = (
    ("https://www.nasdaqtrader.com/dynamic/symdir/nasdaqtraded.txt", "Symbol"),
    ("https://www.nasdaqtrader.com/dynamic/symdir/otherlisted.txt", "ACT Symbol"),
)
NASDAQ_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    ),
}
EXCLUDED_SECURITY_NAME_MARKERS = (
    "warrant",
    "rights",
    "depositary",
    "unit",
    "etf",
    "etn",
    "preferred",
    "notes",
)
KNOWN_YAHOO_EXCHANGE_SUFFIXES = {
    "AS",
    "AT",
    "AX",
    "BA",
    "BC",
    "BD",
    "BE",
    "BK",
    "BO",
    "BR",
    "CA",
    "CO",
    "DE",
    "DU",
    "F",
    "HA",
    "HE",
    "HK",
    "HM",
    "JK",
    "JO",
    "KL",
    "KS",
    "KQ",
    "L",
    "LS",
    "MC",
    "ME",
    "MI",
    "MU",
    "MX",
    "NS",
    "NZ",
    "OL",
    "PA",
    "PR",
    "QA",
    "SA",
    "SG",
    "SI",
    "SN",
    "SO",
    "SS",
    "ST",
    "SW",
    "SZ",
    "T",
    "TA",
    "TO",
    "TW",
    "TWO",
    "V",
    "VI",
    "WA",
}


class YahooFinanceProvider(MarketDataProvider):
    def __init__(
        self,
        *,
        max_workers: int = 20,
        hourly_rate_limit: int = 2_000,
        cache_dir: str | Path | None = None,
        cache_ttl_hours: float = 24.0,
        use_cache: bool = True,
        refresh_cache: bool = False,
    ) -> None:
        self.max_workers = max_workers
        self.snapshot_workers = min(max_workers, 4)
        self.rate_limiter = RateLimiter(max_calls=hourly_rate_limit)
        self.session = curl_requests.Session(impersonate="chrome")
        self.use_cache = use_cache
        self.refresh_cache = refresh_cache
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "greenblatt-magic"
        self.snapshot_cache_dir = self.cache_dir / "snapshots"
        if self.use_cache:
            self.snapshot_cache_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_cache: dict[str, SecuritySnapshot] = {}
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    def get_snapshots(
        self,
        tickers: list[str] | tuple[str, ...],
        *,
        as_of: date | None = None,
        include_momentum: bool = True,
    ) -> list[SecuritySnapshot]:
        universe = list(dict.fromkeys(self._normalize_symbol(ticker) for ticker in tickers if ticker))
        momentum_map: dict[str, float | None] = {}
        if include_momentum and universe:
            momentum_map = self._build_momentum_map(universe, as_of=as_of)

        snapshots: list[SecuritySnapshot] = []
        failures: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=self.snapshot_workers) as executor:
            futures = {
                executor.submit(self._fetch_snapshot, ticker, as_of=as_of): ticker
                for ticker in universe
            }
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    snapshot = future.result()
                except Exception as exc:
                    failures[ticker] = str(exc)
                    continue
                snapshot.momentum_6m = momentum_map.get(ticker)
                snapshots.append(snapshot)
        if not snapshots and failures:
            sample = "; ".join(f"{ticker}: {reason}" for ticker, reason in list(failures.items())[:3])
            raise RuntimeError(
                "Yahoo Finance fundamentals requests are currently being rejected or rate-limited. "
                "This is usually a temporary throttle rather than a permanent blacklist. "
                "Wait 15-60 minutes, then retry with a smaller universe such as "
                "`--candidate-limit 100` or `--candidate-limit 250`. "
                f"Sample failures: {sample}"
            )
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
        start_date = parse_date(start)
        end_date = parse_date(end)
        universe = list(dict.fromkeys(self._normalize_symbol(ticker) for ticker in tickers if ticker))
        if not universe:
            return pd.DataFrame()

        self.rate_limiter.wait()
        data = retry(
            yf.download,
            tickers=universe,
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            interval=interval,
            auto_adjust=auto_adjust,
            progress=False,
            threads=self.max_workers,
            group_by="column",
        )
        if data.empty:
            return pd.DataFrame()
        return self._extract_price_frame(data, field="Adj Close" if not auto_adjust else "Close", tickers=universe)

    def get_us_equity_candidates(self, *, limit: int = 3_000) -> list[str]:
        try:
            rows = self._fetch_nasdaq_stock_screener_rows()
        except RetryError:
            rows = []

        ranked = self._rank_nasdaq_stock_rows(rows)
        if len(ranked) >= limit:
            return ranked[:limit]

        fallback = self._fetch_nasdaq_directory_tickers()
        seen = set(ranked)
        for ticker in fallback:
            if ticker in seen:
                continue
            ranked.append(ticker)
            seen.add(ticker)
            if len(ranked) >= limit:
                break
        return ranked[:limit]

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
        self.rate_limiter.wait()
        instrument = yf.Ticker(ticker)
        info = self._load_info(instrument)
        fast_info = self._load_fast_info(instrument)
        financials = self._load_frame(
            lambda: instrument.financials,
            lambda: instrument.quarterly_financials,
        )
        balance_sheet = self._load_frame(
            lambda: instrument.balance_sheet,
            lambda: instrument.quarterly_balance_sheet,
        )
        if not info and financials.empty and balance_sheet.empty:
            raise RuntimeError(f"{ticker}: Yahoo returned no usable fundamentals")

        return SecuritySnapshot(
            ticker=ticker,
            company_name=_clean_string(info.get("longName") or info.get("shortName")) or ticker,
            sector=_clean_string(info.get("sector") or info.get("sectorDisp")),
            industry=_clean_string(info.get("industry") or info.get("industryDisp")),
            country=_clean_string(info.get("country")),
            exchange=_clean_string(info.get("exchange") or info.get("fullExchangeName") or _fast_info_value(fast_info, "exchange")),
            quote_type=_clean_string(info.get("quoteType") or _fast_info_value(fast_info, "quoteType")),
            is_adr=bool(info.get("isAdr")) or str(info.get("quoteType", "")).upper() == "ADR" or "ADR" in str(info.get("longName", "")).upper(),
            market_cap=_as_float(info.get("marketCap")) or _as_float(_fast_info_value(fast_info, "marketCap")),
            ebit=self._extract_value(financials, FINANCIAL_ROW_ALIASES["ebit"]),
            current_assets=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["current_assets"]),
            current_liabilities=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["current_liabilities"]),
            cash_and_equivalents=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["cash_and_equivalents"]),
            excess_cash=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["cash_and_equivalents"]),
            total_debt=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["total_debt"]),
            minority_interest=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["minority_interest"]),
            preferred_stock=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["preferred_stock"]),
            net_pp_e=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["net_pp_e"]),
            goodwill=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["goodwill"]),
            other_intangibles=self._extract_value(balance_sheet, BALANCE_ROW_ALIASES["other_intangibles"]),
            as_of=as_of or date.today(),
            metadata={
                "currency": info.get("financialCurrency") or info.get("currency"),
                "long_business_summary": info.get("longBusinessSummary"),
            },
        )

    @staticmethod
    def _load_info(instrument: yf.Ticker) -> dict[str, Any]:
        try:
            info = retry(lambda: instrument.info, max_attempts=3, backoff_factor=1.0)
        except (RetryError, YFRateLimitError):
            return {}
        return info if isinstance(info, dict) else {}

    @staticmethod
    def _load_fast_info(instrument: yf.Ticker) -> Any:
        try:
            return instrument.fast_info
        except Exception:
            return None

    @staticmethod
    def _load_frame(*loaders: Any) -> pd.DataFrame:
        for loader in loaders:
            try:
                frame = retry(loader, max_attempts=3, backoff_factor=1.0)
            except (RetryError, YFRateLimitError):
                continue
            if frame is not None and not frame.empty:
                return frame
        return pd.DataFrame()

    def _fetch_nasdaq_stock_screener_rows(self) -> list[dict[str, Any]]:
        self.rate_limiter.wait()
        response = retry(
            self.session.get,
            NASDAQ_STOCK_SCREENER_URL,
            headers=NASDAQ_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or {}
        rows = data.get("rows") or []
        if not isinstance(rows, list):
            return []
        return rows

    def _fetch_nasdaq_directory_tickers(self) -> list[str]:
        tickers: list[str] = []
        seen: set[str] = set()
        for url, symbol_column in NASDAQ_DIRECTORY_URLS:
            self.rate_limiter.wait()
            response = retry(self.session.get, url, headers=NASDAQ_HEADERS, timeout=30)
            response.raise_for_status()
            text = response.text
            rows = self._parse_pipe_delimited_rows(text)
            for row in rows:
                ticker = self._normalize_symbol(str(row.get(symbol_column, "")).strip())
                name = str(row.get("Security Name", "")).strip()
                if not self._is_candidate_symbol(ticker) or not self._is_candidate_security_name(name):
                    continue
                if (row.get("ETF") or "").strip().upper() == "Y":
                    continue
                if (row.get("Test Issue") or "").strip().upper() == "Y":
                    continue
                if ticker in seen:
                    continue
                tickers.append(ticker)
                seen.add(ticker)
        return tickers

    @staticmethod
    def _rank_nasdaq_stock_rows(rows: list[dict[str, Any]]) -> list[str]:
        ranked: list[tuple[str, float]] = []
        for row in rows:
            ticker = YahooFinanceProvider._normalize_symbol(str(row.get("symbol", "")).strip())
            name = str(row.get("name", "")).strip()
            market_cap = _as_float(row.get("marketCap"))
            if not YahooFinanceProvider._is_candidate_symbol(ticker):
                continue
            if not YahooFinanceProvider._is_candidate_security_name(name):
                continue
            if market_cap is None or market_cap <= 0:
                continue
            ranked.append((ticker, market_cap))

        ranked.sort(key=lambda item: item[1], reverse=True)
        deduped: list[str] = []
        seen: set[str] = set()
        for ticker, _ in ranked:
            if ticker in seen:
                continue
            deduped.append(ticker)
            seen.add(ticker)
        return deduped

    @staticmethod
    def _parse_pipe_delimited_rows(text: str) -> list[dict[str, str]]:
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("File Creation Time:"):
                continue
            lines.append(line)
        return list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter="|"))

    @staticmethod
    def _is_candidate_symbol(ticker: str) -> bool:
        if not ticker:
            return False
        return "^" not in ticker and "/" not in ticker and ticker != "FILE CREATION TIME:"

    @staticmethod
    def _is_candidate_security_name(name: str) -> bool:
        lowered = name.lower()
        return not any(marker in lowered for marker in EXCLUDED_SECURITY_NAME_MARKERS)

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
    def _extract_value(frame: pd.DataFrame | None, aliases: list[str]) -> float | None:
        if frame is None or frame.empty:
            return None
        normalized = {str(index).strip().lower(): index for index in frame.index}
        for alias in aliases:
            row_key = normalized.get(alias.strip().lower())
            if row_key is None:
                continue
            series = frame.loc[row_key]
            if isinstance(series, pd.DataFrame):
                series = series.iloc[0]
            series = pd.Series(series).dropna()
            if series.empty:
                continue
            return _as_float(series.iloc[0])
        return None

    @staticmethod
    def _extract_price_frame(data: pd.DataFrame, *, field: str, tickers: list[str]) -> pd.DataFrame:
        if not isinstance(data.columns, pd.MultiIndex):
            column = field if field in data.columns else "Close"
            frame = data[[column]].copy()
            frame.columns = [tickers[0]]
            return frame.sort_index()

        for level in (0, 1):
            try:
                frame = data.xs(field, level=level, axis=1)
            except KeyError:
                continue
            if isinstance(frame, pd.Series):
                frame = frame.to_frame(name=tickers[0])
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = frame.columns.get_level_values(0)
            return frame.sort_index()

        fallback = data.xs("Close", level=0, axis=1)
        if isinstance(fallback, pd.Series):
            fallback = fallback.to_frame(name=tickers[0])
        return fallback.sort_index()

    @staticmethod
    def _normalize_symbol(ticker: str) -> str:
        normalized = ticker.strip().upper()
        if not normalized or normalized.startswith("^") or "=" in normalized or "." not in normalized:
            return normalized

        base, suffix = normalized.rsplit(".", 1)
        if suffix in KNOWN_YAHOO_EXCHANGE_SUFFIXES:
            return f"{base}.{suffix}"
        if any(char.isdigit() for char in base):
            return f"{base}.{suffix}"
        if len(suffix) > 1:
            return f"{base}.{suffix}"
        return normalized.replace(".", "-")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _fast_info_value(fast_info: Any, key: str) -> Any:
    if fast_info is None:
        return None
    try:
        return fast_info.get(key)
    except Exception:
        return None


def _clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
