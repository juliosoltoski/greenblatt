from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

import pandas as pd

from greenblatt.engine import MagicFormulaEngine
from greenblatt.models import BacktestConfig, BacktestResult, ScreenConfig, ScreenResult
from greenblatt.providers.alpha_vantage import AlphaVantageProvider
from greenblatt.providers.base import MarketDataProvider, ProviderHealth
from greenblatt.providers.errors import ProviderConfigurationError
from greenblatt.providers.failover import FailoverProvider
from greenblatt.providers.yahoo import YahooFinanceProvider
from greenblatt.simulation import MagicFormulaBacktester
from greenblatt.universe import UniverseProfile, list_profiles, load_custom_universe, resolve_profile


UniverseSource = Literal["profile", "universe_file", "tickers"]
ProviderFactory = Callable[["ProviderConfig"], MarketDataProvider]
EngineFactory = Callable[[], MagicFormulaEngine]
BacktesterFactory = Callable[[MarketDataProvider], MagicFormulaBacktester]

DEFAULT_PROVIDER_NAME = "yahoo"
ALPHA_VANTAGE_DEFAULT_BASE_URL = "https://www.alphavantage.co/query"


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    key: str
    label: str
    description: str
    supports_historical_fundamentals: bool
    requires_credentials: bool = False


@dataclass(slots=True)
class ProviderConfig:
    provider_name: str = DEFAULT_PROVIDER_NAME
    fallback_provider_name: str | None = None
    use_cache: bool = True
    refresh_cache: bool = False
    cache_ttl_hours: float = 24.0


@dataclass(slots=True)
class UniverseRequest:
    profile: str | None = None
    universe_file: str | Path | None = None
    tickers: Sequence[str] | None = None
    candidate_limit: int | None = None

    def __post_init__(self) -> None:
        selected = int(self.profile is not None) + int(self.universe_file is not None) + int(self.tickers is not None)
        if selected != 1:
            raise ValueError("UniverseRequest requires exactly one of profile, universe_file, or tickers")
        if self.candidate_limit is not None and self.candidate_limit <= 0:
            raise ValueError("candidate_limit must be positive when provided")
        if isinstance(self.tickers, str):
            raise TypeError("tickers must be a sequence of strings, not a comma-delimited string")
        if self.tickers is not None:
            normalized = tuple(ticker.strip() for ticker in self.tickers if ticker and ticker.strip())
            if not normalized:
                raise ValueError("tickers cannot be empty")
            self.tickers = normalized


@dataclass(slots=True)
class ResolvedUniverse:
    source_type: UniverseSource
    source_value: str | None
    tickers: list[str]
    total_candidates: int
    candidate_limit: int | None = None

    @property
    def resolved_count(self) -> int:
        return len(self.tickers)


@dataclass(slots=True)
class ScreenRequest:
    universe: UniverseRequest
    config: ScreenConfig = field(default_factory=ScreenConfig)
    provider: ProviderConfig = field(default_factory=ProviderConfig)


@dataclass(slots=True)
class ScreenResponse:
    request: ScreenRequest
    resolved_universe: ResolvedUniverse
    result: ScreenResult
    ranked_frame: pd.DataFrame
    ranked_rows: list[dict[str, object | None]]
    excluded_rows: list[dict[str, object | None]]


@dataclass(slots=True)
class BacktestRequest:
    universe: UniverseRequest
    config: BacktestConfig
    provider: ProviderConfig = field(default_factory=ProviderConfig)


@dataclass(slots=True)
class BacktestResponse:
    request: BacktestRequest
    resolved_universe: ResolvedUniverse
    result: BacktestResult
    equity_curve_frame: pd.DataFrame
    trades_frame: pd.DataFrame
    trade_summary_frame: pd.DataFrame | None
    review_targets_frame: pd.DataFrame | None
    final_holdings_frame: pd.DataFrame
    summary_payload: dict[str, object | None]
    equity_curve_rows: list[dict[str, object | None]]
    trade_rows: list[dict[str, object | None]]
    trade_summary_rows: list[dict[str, object | None]]
    review_target_rows: list[dict[str, object | None]]
    final_holding_rows: list[dict[str, object | None]]


def build_yahoo_provider(config: ProviderConfig) -> MarketDataProvider:
    return YahooFinanceProvider(
        use_cache=config.use_cache,
        refresh_cache=config.refresh_cache,
        cache_ttl_hours=config.cache_ttl_hours,
    )


build_yahoo_provider.provider_name = "yahoo"


def build_alpha_vantage_provider(config: ProviderConfig) -> MarketDataProvider:
    return AlphaVantageProvider(
        api_key=os.getenv("ALPHA_VANTAGE_API_KEY", ""),
        base_url=os.getenv("ALPHA_VANTAGE_BASE_URL", ALPHA_VANTAGE_DEFAULT_BASE_URL),
        max_calls_per_minute=_env_int("ALPHA_VANTAGE_MAX_CALLS_PER_MINUTE", 5),
        use_cache=config.use_cache,
        refresh_cache=config.refresh_cache,
        cache_ttl_hours=config.cache_ttl_hours,
    )


build_alpha_vantage_provider.provider_name = "alpha_vantage"


PROVIDER_DESCRIPTORS: dict[str, ProviderDescriptor] = {
    "yahoo": ProviderDescriptor(
        key="yahoo",
        label="Yahoo Finance",
        description="Unauthenticated market data access through yfinance and NASDAQ directory helpers.",
        supports_historical_fundamentals=YahooFinanceProvider.supports_historical_fundamentals,
        requires_credentials=False,
    ),
    "alpha_vantage": ProviderDescriptor(
        key="alpha_vantage",
        label="Alpha Vantage",
        description="API-key-backed market data access with fundamentals, daily prices, and explicit rate limits.",
        supports_historical_fundamentals=AlphaVantageProvider.supports_historical_fundamentals,
        requires_credentials=True,
    ),
}
PROVIDER_FACTORIES: dict[str, ProviderFactory] = {
    "yahoo": build_yahoo_provider,
    "alpha_vantage": build_alpha_vantage_provider,
}


def normalize_provider_name(name: str | None, *, default: str = DEFAULT_PROVIDER_NAME) -> str:
    raw = (name or default).strip().lower().replace("-", "_")
    if raw not in PROVIDER_FACTORIES:
        supported = ", ".join(sorted(PROVIDER_FACTORIES))
        raise ValueError(f"Unsupported provider '{name}'. Supported providers: {supported}.")
    return raw


def serialize_provider_config(config: ProviderConfig) -> dict[str, object]:
    provider_name = normalize_provider_name(config.provider_name)
    fallback_provider_name = config.fallback_provider_name
    if fallback_provider_name:
        fallback_provider_name = normalize_provider_name(fallback_provider_name)
        if fallback_provider_name == provider_name:
            fallback_provider_name = None
    return {
        "provider_name": provider_name,
        "fallback_provider_name": fallback_provider_name,
        "use_cache": bool(config.use_cache),
        "refresh_cache": bool(config.refresh_cache),
        "cache_ttl_hours": float(config.cache_ttl_hours),
    }


def provider_config_from_payload(
    payload: Mapping[str, Any] | None,
    *,
    default_provider_name: str = DEFAULT_PROVIDER_NAME,
    default_fallback_provider_name: str | None = None,
    default_use_cache: bool = True,
    default_refresh_cache: bool = False,
    default_cache_ttl_hours: float = 24.0,
) -> ProviderConfig:
    data = payload or {}
    provider_name = normalize_provider_name(_coerce_string(data.get("provider_name")), default=default_provider_name)
    fallback_provider_name = _coerce_string(data.get("fallback_provider_name")) or default_fallback_provider_name
    if fallback_provider_name:
        fallback_provider_name = normalize_provider_name(fallback_provider_name)
        if fallback_provider_name == provider_name:
            fallback_provider_name = None
    return ProviderConfig(
        provider_name=provider_name,
        fallback_provider_name=fallback_provider_name,
        use_cache=_coerce_bool(data.get("use_cache"), default_use_cache),
        refresh_cache=_coerce_bool(data.get("refresh_cache"), default_refresh_cache),
        cache_ttl_hours=_coerce_float(data.get("cache_ttl_hours"), default_cache_ttl_hours),
    )


def list_provider_descriptors() -> list[dict[str, object]]:
    return [
        {
            "key": descriptor.key,
            "label": descriptor.label,
            "description": descriptor.description,
            "supports_historical_fundamentals": descriptor.supports_historical_fundamentals,
            "requires_credentials": descriptor.requires_credentials,
        }
        for descriptor in PROVIDER_DESCRIPTORS.values()
    ]


def build_provider(config: ProviderConfig) -> MarketDataProvider:
    serialized = serialize_provider_config(config)
    primary_name = str(serialized["provider_name"])
    primary = PROVIDER_FACTORIES[primary_name](config)
    fallback_name = serialized["fallback_provider_name"]
    if not fallback_name:
        return primary
    fallback_config = ProviderConfig(
        provider_name=str(fallback_name),
        use_cache=bool(serialized["use_cache"]),
        refresh_cache=bool(serialized["refresh_cache"]),
        cache_ttl_hours=float(serialized["cache_ttl_hours"]),
    )
    fallback = PROVIDER_FACTORIES[str(fallback_name)](fallback_config)
    return FailoverProvider(primary, fallback)


build_provider.provider_name = "provider"


def provider_result_payload(provider: MarketDataProvider, config: ProviderConfig) -> dict[str, object | None]:
    serialized = serialize_provider_config(config)
    resolved_provider_name = getattr(provider, "resolved_provider_name", None) or getattr(provider, "provider_name", None)
    if isinstance(resolved_provider_name, str):
        try:
            resolved_provider_name = normalize_provider_name(resolved_provider_name)
        except ValueError:
            resolved_provider_name = resolved_provider_name.strip().lower() or None
    return {
        "provider_name": serialized["provider_name"],
        "fallback_provider_name": serialized["fallback_provider_name"],
        "resolved_provider_name": resolved_provider_name,
        "fallback_used": bool(getattr(provider, "fallback_used", False)),
        "supports_historical_fundamentals": bool(getattr(provider, "supports_historical_fundamentals", False)),
    }


def provider_health_payload(
    config: ProviderConfig | None = None,
    *,
    probe: bool = False,
) -> dict[str, object]:
    requested_config = config or ProviderConfig()
    serialized_request = serialize_provider_config(requested_config)
    providers: list[dict[str, object | None]] = []
    for descriptor in list_provider_descriptors():
        provider_name = str(descriptor["key"])
        health_config = ProviderConfig(
            provider_name=provider_name,
            use_cache=requested_config.use_cache,
            refresh_cache=requested_config.refresh_cache,
            cache_ttl_hours=requested_config.cache_ttl_hours,
        )
        try:
            health = PROVIDER_FACTORIES[provider_name](health_config).check_health(probe=probe)
        except ProviderConfigurationError as exc:
            health = ProviderHealth(
                provider_name=provider_name,
                state="unconfigured",
                detail=str(exc),
                supports_historical_fundamentals=bool(descriptor["supports_historical_fundamentals"]),
            )
        except Exception as exc:
            health = ProviderHealth(
                provider_name=provider_name,
                state="error",
                detail=str(exc),
                supports_historical_fundamentals=bool(descriptor["supports_historical_fundamentals"]),
            )
        providers.append(
            {
                **descriptor,
                "state": health.state,
                "detail": health.detail,
                "configured_default": provider_name == serialized_request["provider_name"],
                "configured_fallback": provider_name == serialized_request["fallback_provider_name"],
            }
        )
    return {
        "default_provider": serialized_request["provider_name"],
        "fallback_provider": serialized_request["fallback_provider_name"],
        "providers": providers,
    }


def normalize_payload(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): normalize_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_payload(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            value = value.item()
        except (AttributeError, TypeError, ValueError):
            pass
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value


def records_from_rows(rows: Sequence[object]) -> list[dict[str, object | None]]:
    records: list[dict[str, object | None]] = []
    for row in rows:
        if is_dataclass(row):
            raw = asdict(row)
        elif isinstance(row, dict):
            raw = row
        else:
            raise TypeError("records_from_rows only supports dataclasses and dictionaries")
        normalized = normalize_payload(raw)
        assert isinstance(normalized, dict)
        records.append(normalized)
    return records


def frame_to_records(frame: pd.DataFrame | None) -> list[dict[str, object | None]]:
    if frame is None or frame.empty:
        return []
    records = frame.to_dict(orient="records")
    return records_from_rows(records)


class UniverseService:
    def list_profiles(self) -> list[UniverseProfile]:
        return list_profiles()

    def resolve(self, request: UniverseRequest, provider: MarketDataProvider) -> ResolvedUniverse:
        source_type: UniverseSource
        source_value: str | None
        try:
            if request.profile is not None:
                source_type = "profile"
                source_value = request.profile
                tickers = resolve_profile(provider, request.profile)
            elif request.universe_file is not None:
                source_type = "universe_file"
                source_value = str(request.universe_file)
                tickers = load_custom_universe(request.universe_file)
            else:
                source_type = "tickers"
                source_value = None
                tickers = [ticker.strip() for ticker in request.tickers or () if ticker.strip()]
        except KeyError as exc:
            raise ValueError(str(exc)) from exc

        total_candidates = len(tickers)
        if request.candidate_limit:
            tickers = tickers[: request.candidate_limit]
        return ResolvedUniverse(
            source_type=source_type,
            source_value=source_value,
            tickers=tickers,
            total_candidates=total_candidates,
            candidate_limit=request.candidate_limit,
        )


class ScreenService:
    def __init__(
        self,
        *,
        provider_factory: ProviderFactory = build_provider,
        universe_service: UniverseService | None = None,
        engine_factory: EngineFactory = MagicFormulaEngine,
    ) -> None:
        self.provider_factory = provider_factory
        self.universe_service = universe_service or UniverseService()
        self.engine_factory = engine_factory

    def run(self, request: ScreenRequest, provider: MarketDataProvider | None = None) -> ScreenResponse:
        active_provider = provider or self.provider_factory(request.provider)
        resolved_universe = self.universe_service.resolve(request.universe, active_provider)
        engine = self.engine_factory()
        result = engine.screen(
            active_provider.get_snapshots(
                resolved_universe.tickers,
                include_momentum=request.config.momentum_mode != "none",
            ),
            request.config,
        )
        ranked_frame = engine.to_frame(result)
        return ScreenResponse(
            request=request,
            resolved_universe=resolved_universe,
            result=result,
            ranked_frame=ranked_frame,
            ranked_rows=frame_to_records(ranked_frame),
            excluded_rows=records_from_rows(result.excluded),
        )


class BacktestService:
    def __init__(
        self,
        *,
        provider_factory: ProviderFactory = build_provider,
        universe_service: UniverseService | None = None,
        backtester_factory: BacktesterFactory = MagicFormulaBacktester,
    ) -> None:
        self.provider_factory = provider_factory
        self.universe_service = universe_service or UniverseService()
        self.backtester_factory = backtester_factory

    def run(self, request: BacktestRequest, provider: MarketDataProvider | None = None) -> BacktestResponse:
        active_provider = provider or self.provider_factory(request.provider)
        resolved_universe = self.universe_service.resolve(request.universe, active_provider)
        backtester = self.backtester_factory(active_provider)
        result = backtester.run(resolved_universe.tickers, request.config)
        equity_curve_frame = result.equity_curve
        trades_frame = result.trades
        trade_summary_frame = result.trade_summary
        review_targets_frame = result.review_targets
        final_holdings_frame = type(backtester).build_final_holdings_frame(result.holdings)
        summary_payload = normalize_payload(result.summary)
        assert isinstance(summary_payload, dict)
        return BacktestResponse(
            request=request,
            resolved_universe=resolved_universe,
            result=result,
            equity_curve_frame=equity_curve_frame,
            trades_frame=trades_frame,
            trade_summary_frame=trade_summary_frame,
            review_targets_frame=review_targets_frame,
            final_holdings_frame=final_holdings_frame,
            summary_payload=summary_payload,
            equity_curve_rows=frame_to_records(equity_curve_frame),
            trade_rows=frame_to_records(trades_frame),
            trade_summary_rows=frame_to_records(trade_summary_frame),
            review_target_rows=frame_to_records(review_targets_frame),
            final_holding_rows=frame_to_records(final_holdings_frame),
        )


def _coerce_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _coerce_float(value: object, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default
