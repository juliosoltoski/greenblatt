from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.conf import settings

from greenblatt.services import ProviderConfig, provider_config_from_payload, provider_health_payload


def default_provider_config(
    *,
    use_cache: bool = True,
    refresh_cache: bool = False,
    cache_ttl_hours: float = 24.0,
) -> ProviderConfig:
    return ProviderConfig(
        provider_name=settings.MARKET_DATA_PROVIDER,
        fallback_provider_name=settings.MARKET_DATA_PROVIDER_FALLBACK,
        use_cache=use_cache,
        refresh_cache=refresh_cache,
        cache_ttl_hours=cache_ttl_hours,
    )


def provider_config_from_request_payload(
    payload: Mapping[str, Any] | None,
    *,
    use_cache: bool,
    refresh_cache: bool,
    cache_ttl_hours: float,
) -> ProviderConfig:
    return provider_config_from_payload(
        payload,
        default_provider_name=settings.MARKET_DATA_PROVIDER,
        default_fallback_provider_name=settings.MARKET_DATA_PROVIDER_FALLBACK,
        default_use_cache=use_cache,
        default_refresh_cache=refresh_cache,
        default_cache_ttl_hours=cache_ttl_hours,
    )


def configured_provider_health_payload(*, probe: bool = False) -> dict[str, object]:
    return provider_health_payload(default_provider_config(), probe=probe)
