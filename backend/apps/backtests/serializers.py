from __future__ import annotations

from rest_framework import serializers


class BacktestLaunchSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    universe_id = serializers.IntegerField(min_value=1)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    initial_capital = serializers.FloatField(required=False, default=100_000.0, min_value=1)
    portfolio_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=200)
    review_frequency = serializers.CharField(required=False, default="W-FRI", max_length=32)
    benchmark = serializers.CharField(required=False, allow_blank=True, default="^GSPC", max_length=32)
    momentum_mode = serializers.ChoiceField(
        choices=[("none", "none"), ("overlay", "overlay"), ("filter", "filter")],
        required=False,
        default="none",
    )
    sector_allowlist = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        allow_empty=True,
    )
    min_market_cap = serializers.FloatField(required=False, allow_null=True, min_value=0)
    use_cache = serializers.BooleanField(required=False, default=True)
    refresh_cache = serializers.BooleanField(required=False, default=False)
    cache_ttl_hours = serializers.FloatField(required=False, default=24.0, min_value=0)

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "End date must be on or after the start date."})
        return attrs

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


class BacktestRunListSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100)
    job_state = serializers.CharField(required=False, allow_blank=True)
