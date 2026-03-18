from __future__ import annotations

import re
from typing import Any

try:
    from billiard.exceptions import SoftTimeLimitExceeded
except ImportError:  # pragma: no cover
    SoftTimeLimitExceeded = TimeoutError  # type: ignore[assignment]

try:
    from requests import RequestException
except ImportError:  # pragma: no cover
    RequestException = OSError  # type: ignore[assignment]


class RetryableJobError(RuntimeError):
    def __init__(self, message: str, *, error_code: str = "retryable_error") -> None:
        super().__init__(message)
        self.error_code = error_code


TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RetryableJobError,
    ConnectionError,
    TimeoutError,
    OSError,
    SoftTimeLimitExceeded,
    RequestException,
)


def is_retryable_exception(exc: BaseException) -> bool:
    return isinstance(exc, TRANSIENT_EXCEPTIONS)


def next_retry_delay_seconds(retry_index: int, *, base_delay: int = 5, max_delay: int = 300) -> int:
    return min(max_delay, base_delay * (2**retry_index))


def error_code_for_exception(exc: BaseException) -> str:
    explicit = getattr(exc, "error_code", None)
    if explicit:
        return str(explicit)
    name = exc.__class__.__name__
    snake_case = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return snake_case or "job_failed"


def merge_metadata(base: dict[str, Any] | None, updates: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(base or {})
    if updates:
        merged.update(updates)
    return merged
