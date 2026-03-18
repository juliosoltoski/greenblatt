from __future__ import annotations

from rest_framework import serializers


class ScreenLaunchSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    universe_id = serializers.IntegerField(min_value=1)
    top_n = serializers.IntegerField(required=False, default=30, min_value=1, max_value=500)
    momentum_mode = serializers.ChoiceField(
        choices=[
            ("none", "none"),
            ("overlay", "overlay"),
            ("filter", "filter"),
        ],
        required=False,
        default="none",
    )
    sector_allowlist = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        allow_empty=True,
    )
    min_market_cap = serializers.FloatField(required=False, allow_null=True, min_value=0)
    exclude_financials = serializers.BooleanField(required=False, default=True)
    exclude_utilities = serializers.BooleanField(required=False, default=True)
    exclude_adrs = serializers.BooleanField(required=False, default=True)
    use_cache = serializers.BooleanField(required=False, default=True)
    refresh_cache = serializers.BooleanField(required=False, default=False)
    cache_ttl_hours = serializers.FloatField(required=False, default=24.0, min_value=0)

    def validate_sector_allowlist(self, value: list[str]) -> list[str]:
        normalized = []
        seen: set[str] = set()
        for item in value:
            cleaned = item.strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(cleaned)
        return normalized


class PagingSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=25, min_value=1, max_value=100)
    sort = serializers.CharField(required=False, allow_blank=True)
    direction = serializers.ChoiceField(choices=[("asc", "asc"), ("desc", "desc")], required=False, default="asc")


class ScreenRunListSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100)
    job_state = serializers.CharField(required=False, allow_blank=True)
