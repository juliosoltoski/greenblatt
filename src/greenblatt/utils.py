from __future__ import annotations

import csv
import math
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TypeVar

import pandas as pd


T = TypeVar("T")


class RateLimiter:
    """Simple sliding-window limiter for Yahoo's unofficial hourly ceiling."""

    def __init__(self, max_calls: int = 2_000, window_seconds: int = 3_600) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        while True:
            with self._lock:
                now = time.time()
                while self._calls and now - self._calls[0] > self.window_seconds:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                sleep_for = max(0.1, self.window_seconds - (now - self._calls[0]))
            time.sleep(min(sleep_for, 5.0))


class RetryError(RuntimeError):
    pass


def retry(
    fn: Callable[..., T],
    *args: object,
    max_attempts: int = 5,
    backoff_factor: float = 0.5,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    **kwargs: object,
) -> T:
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except exceptions as exc:
            attempt += 1
            if attempt >= max_attempts:
                raise RetryError(str(exc)) from exc
            delay = backoff_factor * (2 ** (attempt - 1))
            time.sleep(delay)


def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def previous_available_price(price_frame: pd.DataFrame, when: pd.Timestamp, ticker: str) -> float | None:
    if ticker not in price_frame.columns:
        return None
    series = price_frame[ticker].dropna()
    series = series[series.index <= when]
    if series.empty:
        return None
    return float(series.iloc[-1])


def closest_available_date(index: pd.Index, when: pd.Timestamp) -> pd.Timestamp | None:
    valid = index[index >= when]
    if len(valid) == 0:
        valid = index[index <= when]
    if len(valid) == 0:
        return None
    return pd.Timestamp(valid[0])


def rows_to_csv(path: str | Path, rows: Iterable[object]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    iterator = list(rows)
    if not iterator:
        target.write_text("", encoding="utf-8")
        return

    first = iterator[0]
    if is_dataclass(first):
        fieldnames = list(asdict(first).keys())
        records = [asdict(row) for row in iterator]
    elif isinstance(first, dict):
        fieldnames = list(first.keys())
        records = iterator
    else:
        raise TypeError("rows_to_csv only supports dataclasses or dicts")

    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def annualized_return(total_return: float, days: int) -> float | None:
    if days <= 0 or total_return <= -1:
        return None
    return math.pow(1 + total_return, 365 / days) - 1
