from __future__ import annotations

from rest_framework import serializers

from greenblatt.services import normalize_provider_name


class ProviderCacheWarmLaunchSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False)
    universe_id = serializers.IntegerField()
    sample_size = serializers.IntegerField(min_value=1, max_value=500, default=100)
    refresh_cache = serializers.BooleanField(required=False, default=False)
    cache_ttl_hours = serializers.FloatField(required=False, min_value=1.0, max_value=168.0, default=24.0)
    provider_name = serializers.CharField(required=False, allow_blank=True, max_length=64)
    fallback_provider_name = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate_provider_name(self, value: str) -> str:
        return _validate_provider_choice(value)

    def validate_fallback_provider_name(self, value: str) -> str:
        return _validate_provider_choice(value)


def _validate_provider_choice(value: str) -> str:
    if not value:
        return ""
    try:
        return normalize_provider_name(value)
    except ValueError as exc:
        raise serializers.ValidationError(str(exc)) from exc
