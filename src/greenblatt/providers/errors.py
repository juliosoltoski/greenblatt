from __future__ import annotations


PROVIDER_MODULE_HINT_PREFIXES = (
    "greenblatt.providers",
    "yfinance",
    "curl_cffi",
    "requests",
)
PROVIDER_MESSAGE_HINTS = (
    "alpha vantage",
    "alphavantage",
    "api key",
    "market data provider",
    "rate limit",
    "rate-limit",
    "yahoo",
)


class ProviderError(RuntimeError):
    pass


class ProviderConfigurationError(ProviderError):
    pass


class ProviderResponseError(ProviderError):
    pass


class ProviderRateLimitError(ProviderResponseError):
    pass


def is_provider_exception(exc: BaseException) -> bool:
    if isinstance(exc, ProviderError):
        return True
    module_name = exc.__class__.__module__
    if module_name.startswith(PROVIDER_MODULE_HINT_PREFIXES):
        return True
    message = str(exc).lower()
    return any(hint in message for hint in PROVIDER_MESSAGE_HINTS)
