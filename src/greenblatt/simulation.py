from __future__ import annotations

from dataclasses import asdict, replace
from datetime import timedelta
from typing import Iterable

import pandas as pd

from greenblatt.engine import MagicFormulaEngine
from greenblatt.models import BacktestConfig, BacktestResult, Holding, ScreenConfig, SecuritySnapshot, Trade
from greenblatt.providers.base import MarketDataProvider
from greenblatt.utils import annualized_return, closest_available_date, previous_available_price


class MagicFormulaBacktester:
    def __init__(self, provider: MarketDataProvider, engine: MagicFormulaEngine | None = None) -> None:
        self.provider = provider
        self.engine = engine or MagicFormulaEngine()

    def run(self, universe: Iterable[str], config: BacktestConfig) -> BacktestResult:
        tickers = list(dict.fromkeys(ticker for ticker in universe if ticker))
        if not tickers:
            raise ValueError("Universe cannot be empty")

        history_start = config.start_date - timedelta(days=400)
        prices = self.provider.get_price_history(tickers, start=history_start, end=config.end_date)
        if prices.empty:
            raise ValueError("Price history is empty for the selected universe")

        benchmark_prices = pd.DataFrame()
        if config.benchmark:
            benchmark_prices = self.provider.get_price_history([config.benchmark], start=config.start_date, end=config.end_date)

        price_index = prices.index[(prices.index.date >= config.start_date) & (prices.index.date <= config.end_date)]
        if len(price_index) == 0:
            raise ValueError("No trading days available in the requested date range")

        review_dates = self._resolve_review_dates(price_index, config.review_frequency)
        review_schedule = {timestamp.normalize() for timestamp in review_dates}

        cash = config.initial_capital
        holdings: dict[str, Holding] = {}
        trades: list[Trade] = []
        equity_rows: list[dict[str, float | str | None]] = []
        review_target_rows: list[dict[str, object | None]] = []

        static_snapshots: list[SecuritySnapshot] | None = None
        if not self.provider.supports_historical_fundamentals:
            static_snapshots = self.provider.get_snapshots(tickers, include_momentum=False)

        for current_date in price_index:
            current_date = pd.Timestamp(current_date)
            if current_date.normalize() in review_schedule:
                ranked = self._screen_for_date(
                    tickers=tickers,
                    prices=prices,
                    as_of=current_date,
                    config=config,
                    static_snapshots=static_snapshots,
                )
                review_target_rows.extend(self._build_review_target_rows(current_date, ranked, config.portfolio_size))
                cash, holdings, review_trades = self._rebalance(
                    current_date=current_date,
                    prices=prices,
                    ranked=ranked,
                    holdings=holdings,
                    cash=cash,
                    portfolio_size=config.portfolio_size,
                )
                trades.extend(review_trades)

            equity = cash + self._portfolio_market_value(holdings, prices, current_date)
            row = {
                "date": current_date.date().isoformat(),
                "cash": cash,
                "equity": equity,
                "positions": len(holdings),
            }
            if not benchmark_prices.empty and config.benchmark in benchmark_prices.columns:
                benchmark_price = previous_available_price(benchmark_prices, current_date, config.benchmark)
                first_benchmark = float(benchmark_prices[config.benchmark].dropna().iloc[0])
                row["benchmark_equity"] = (
                    config.initial_capital * (benchmark_price / first_benchmark)
                    if benchmark_price is not None and first_benchmark > 0
                    else None
                )
            equity_rows.append(row)

        equity_curve = pd.DataFrame(equity_rows)
        trades_frame = pd.DataFrame([asdict(trade) for trade in trades])
        review_targets = pd.DataFrame(review_target_rows)
        trade_summary = self._build_trade_summary(trades_frame, holdings)
        summary = self._build_summary(equity_curve, config)
        if not benchmark_prices.empty and "benchmark_equity" in equity_curve:
            benchmark_total_return = equity_curve["benchmark_equity"].dropna().iloc[-1] / config.initial_capital - 1
            summary["benchmark_return"] = benchmark_total_return
            strategy_total_return = summary["total_return"]
            summary["alpha_vs_benchmark"] = strategy_total_return - benchmark_total_return

        return BacktestResult(
            equity_curve=equity_curve,
            trades=trades_frame,
            holdings=holdings,
            summary=summary,
            review_targets=review_targets,
            trade_summary=trade_summary,
        )

    def _screen_for_date(
        self,
        *,
        tickers: list[str],
        prices: pd.DataFrame,
        as_of: pd.Timestamp,
        config: BacktestConfig,
        static_snapshots: list[SecuritySnapshot] | None,
    ) -> list[SecuritySnapshot]:
        if static_snapshots is None:
            snapshots = self.provider.get_snapshots(tickers, as_of=as_of.date(), include_momentum=False)
        else:
            snapshots = [replace(snapshot) for snapshot in static_snapshots]

        if config.momentum_mode != "none":
            snapshots = [self._with_momentum(snapshot, prices, as_of) for snapshot in snapshots]

        screen_result = self.engine.screen(
            snapshots,
            ScreenConfig(
                top_n=len(tickers),
                momentum_mode=config.momentum_mode,
                sector_allowlist=config.sector_allowlist,
                min_market_cap=config.min_market_cap,
            ),
        )
        return screen_result.ranked

    def _with_momentum(self, snapshot: SecuritySnapshot, prices: pd.DataFrame, as_of: pd.Timestamp) -> SecuritySnapshot:
        momentum = None
        if snapshot.ticker in prices.columns:
            series = prices[snapshot.ticker].dropna()
            series = series[series.index <= as_of]
            if len(series) >= 90:
                anchor = as_of - pd.Timedelta(days=182)
                base = series[series.index <= anchor]
                if not base.empty:
                    start_price = float(base.iloc[-1])
                    end_price = float(series.iloc[-1])
                    if start_price > 0:
                        momentum = (end_price / start_price) - 1
        return replace(snapshot, momentum_6m=momentum, as_of=as_of.date())

    @staticmethod
    def _resolve_review_dates(index: pd.Index, frequency: str) -> list[pd.Timestamp]:
        raw_dates = pd.date_range(index[0], index[-1], freq=frequency)
        review_dates: list[pd.Timestamp] = []
        seen: set[pd.Timestamp] = set()
        for raw in raw_dates:
            actual = closest_available_date(index, raw)
            if actual is None:
                continue
            normalized = actual.normalize()
            if normalized in seen:
                continue
            seen.add(normalized)
            review_dates.append(actual)
        if index[0].normalize() not in seen:
            review_dates.insert(0, pd.Timestamp(index[0]))
        return review_dates

    def _rebalance(
        self,
        *,
        current_date: pd.Timestamp,
        prices: pd.DataFrame,
        ranked: list[SecuritySnapshot],
        holdings: dict[str, Holding],
        cash: float,
        portfolio_size: int,
    ) -> tuple[float, dict[str, Holding], list[Trade]]:
        next_holdings = dict(holdings)
        trades: list[Trade] = []
        sold_tickers: set[str] = set()

        for ticker, holding in list(next_holdings.items()):
            price = previous_available_price(prices, current_date, ticker)
            if price is None:
                continue
            holding_period_days = (current_date.date() - holding.entry_date).days
            return_pct = (price / holding.entry_price) - 1 if holding.entry_price else 0.0
            should_sell_loser = holding_period_days >= 51 * 7 and return_pct < 0
            should_sell_winner = holding_period_days >= 53 * 7 and return_pct >= 0
            if should_sell_loser or should_sell_winner:
                proceeds = holding.shares * price
                cash += proceeds
                trades.append(
                    Trade(
                        date=current_date.date(),
                        ticker=ticker,
                        side="SELL",
                        shares=holding.shares,
                        price=price,
                        proceeds=proceeds,
                        reason="51-week loser harvest" if should_sell_loser else "53-week winner realization",
                    )
                )
                sold_tickers.add(ticker)
                del next_holdings[ticker]

        open_slots = portfolio_size - len(next_holdings)
        if open_slots <= 0:
            return cash, next_holdings, trades

        candidates = [
            security
            for security in ranked
            if security.ticker not in next_holdings and security.ticker not in sold_tickers
        ]
        for candidate in candidates:
            if open_slots <= 0 or cash <= 0:
                break
            price = previous_available_price(prices, current_date, candidate.ticker)
            if price is None or price <= 0:
                continue
            allocation = cash / open_slots
            shares = allocation / price
            if shares <= 0:
                continue
            proceeds = shares * price
            cash -= proceeds
            next_holdings[candidate.ticker] = Holding(
                ticker=candidate.ticker,
                shares=shares,
                entry_date=current_date.date(),
                entry_price=price,
                score=candidate.final_score,
            )
            trades.append(
                Trade(
                    date=current_date.date(),
                    ticker=candidate.ticker,
                    side="BUY",
                    shares=shares,
                    price=price,
                    proceeds=proceeds,
                    reason="initial allocation" if len(holdings) == 0 else "rebalance replacement",
                )
            )
            open_slots -= 1

        return cash, next_holdings, trades

    @staticmethod
    def _portfolio_market_value(holdings: dict[str, Holding], prices: pd.DataFrame, current_date: pd.Timestamp) -> float:
        total = 0.0
        for ticker, holding in holdings.items():
            price = previous_available_price(prices, current_date, ticker)
            if price is None:
                continue
            total += holding.shares * price
        return total

    @staticmethod
    def _build_review_target_rows(
        current_date: pd.Timestamp,
        ranked: list[SecuritySnapshot],
        portfolio_size: int,
    ) -> list[dict[str, object | None]]:
        rows: list[dict[str, object | None]] = []
        for target_rank, security in enumerate(ranked[:portfolio_size], start=1):
            rows.append(
                {
                    "date": current_date.date().isoformat(),
                    "target_rank": target_rank,
                    "ticker": security.ticker,
                    "company_name": security.company_name,
                    "sector": security.sector,
                    "industry": security.industry,
                    "final_score": getattr(security, "final_score", None),
                    "composite_score": getattr(security, "composite_score", None),
                    "roc_rank": getattr(security, "roc_rank", None),
                    "ey_rank": getattr(security, "ey_rank", None),
                    "momentum_rank": getattr(security, "momentum_rank", None),
                }
            )
        return rows

    @staticmethod
    def _build_trade_summary(trades: pd.DataFrame, holdings: dict[str, Holding]) -> pd.DataFrame:
        columns = [
            "ticker",
            "first_trade_date",
            "last_trade_date",
            "buy_count",
            "sell_count",
            "net_trade_count",
            "currently_held",
        ]
        if trades.empty:
            return pd.DataFrame(columns=columns)

        rows: list[dict[str, object]] = []
        for ticker, group in trades.groupby("ticker", sort=True):
            buys = int((group["side"] == "BUY").sum())
            sells = int((group["side"] == "SELL").sum())
            rows.append(
                {
                    "ticker": ticker,
                    "first_trade_date": group["date"].iloc[0].isoformat(),
                    "last_trade_date": group["date"].iloc[-1].isoformat(),
                    "buy_count": buys,
                    "sell_count": sells,
                    "net_trade_count": buys - sells,
                    "currently_held": ticker in holdings,
                }
            )
        frame = pd.DataFrame(rows, columns=columns)
        return frame.sort_values(["first_trade_date", "ticker"]).reset_index(drop=True)

    @staticmethod
    def build_final_holdings_frame(holdings: dict[str, Holding]) -> pd.DataFrame:
        rows = [
            {
                "ticker": holding.ticker,
                "shares": holding.shares,
                "entry_date": holding.entry_date.isoformat(),
                "entry_price": holding.entry_price,
                "score": holding.score,
            }
            for holding in holdings.values()
        ]
        if not rows:
            return pd.DataFrame(columns=["ticker", "shares", "entry_date", "entry_price", "score"])
        return pd.DataFrame(rows).sort_values("ticker").reset_index(drop=True)

    @staticmethod
    def _build_summary(equity_curve: pd.DataFrame, config: BacktestConfig) -> dict[str, float | int | str | None]:
        if equity_curve.empty:
            return {
                "start_date": config.start_date.isoformat(),
                "end_date": config.end_date.isoformat(),
                "total_return": 0.0,
                "annualized_return": None,
                "max_drawdown": 0.0,
                "ending_equity": config.initial_capital,
            }

        ending_equity = float(equity_curve["equity"].iloc[-1])
        total_return = ending_equity / config.initial_capital - 1
        rolling_peak = equity_curve["equity"].cummax()
        drawdown = equity_curve["equity"] / rolling_peak - 1
        max_drawdown = float(drawdown.min())
        days = (config.end_date - config.start_date).days
        return {
            "start_date": config.start_date.isoformat(),
            "end_date": config.end_date.isoformat(),
            "total_return": total_return,
            "annualized_return": annualized_return(total_return, days),
            "max_drawdown": max_drawdown,
            "ending_equity": ending_equity,
            "ending_positions": int(equity_curve["positions"].iloc[-1]),
        }
