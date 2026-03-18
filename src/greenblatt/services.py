from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

import pandas as pd

from greenblatt.engine import MagicFormulaEngine
from greenblatt.models import BacktestConfig, BacktestResult, ScreenConfig, ScreenResult
from greenblatt.providers.base import MarketDataProvider
from greenblatt.providers.yahoo import YahooFinanceProvider
from greenblatt.simulation import MagicFormulaBacktester
from greenblatt.universe import UniverseProfile, list_profiles, load_custom_universe, resolve_profile


UniverseSource = Literal["profile", "universe_file", "tickers"]
ProviderFactory = Callable[["ProviderConfig"], MarketDataProvider]
EngineFactory = Callable[[], MagicFormulaEngine]
BacktesterFactory = Callable[[MarketDataProvider], MagicFormulaBacktester]


@dataclass(slots=True)
class ProviderConfig:
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
        provider_factory: ProviderFactory = build_yahoo_provider,
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
        provider_factory: ProviderFactory = build_yahoo_provider,
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
