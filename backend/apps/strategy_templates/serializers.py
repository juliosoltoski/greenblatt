from __future__ import annotations

from rest_framework import serializers

from apps.collaboration.models import ReviewStatus
from apps.strategy_templates.models import StrategyTemplate


class StrategyTemplateListSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    workflow_kind = serializers.ChoiceField(choices=StrategyTemplate.WorkflowKind.choices, required=False)
    review_status = serializers.ChoiceField(choices=ReviewStatus.choices, required=False)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)
    starred_only = serializers.BooleanField(required=False)


class StrategyTemplateCreateSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    workflow_kind = serializers.ChoiceField(choices=StrategyTemplate.WorkflowKind.choices, required=False)
    universe_id = serializers.IntegerField(required=False, min_value=1)
    config = serializers.JSONField(required=False)
    source_screen_run_id = serializers.IntegerField(required=False, min_value=1)
    source_backtest_run_id = serializers.IntegerField(required=False, min_value=1)
    is_starred = serializers.BooleanField(required=False, default=False)
    tags = serializers.ListField(child=serializers.CharField(max_length=50), required=False, allow_empty=True, default=list)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    review_status = serializers.ChoiceField(choices=ReviewStatus.choices, required=False, default=ReviewStatus.DRAFT)
    review_notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        source_screen_run_id = attrs.get("source_screen_run_id")
        source_backtest_run_id = attrs.get("source_backtest_run_id")
        source_count = int(source_screen_run_id is not None) + int(source_backtest_run_id is not None)
        if source_count > 1:
            raise serializers.ValidationError("Choose at most one source run when creating a template.")
        if source_count == 0:
            missing = []
            if not attrs.get("workflow_kind"):
                missing.append("workflow_kind")
            if not attrs.get("universe_id"):
                missing.append("universe_id")
            if "config" not in attrs:
                missing.append("config")
            if missing:
                raise serializers.ValidationError(
                    {"detail": f"Explicit template creation requires: {', '.join(missing)}."}
                )
        return attrs

    def validate_tags(self, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            cleaned = item.strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(cleaned[:50])
        return normalized


class StrategyTemplateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    universe_id = serializers.IntegerField(required=False, min_value=1)
    config = serializers.JSONField(required=False)
    is_starred = serializers.BooleanField(required=False)
    tags = serializers.ListField(child=serializers.CharField(max_length=50), required=False, allow_empty=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    review_status = serializers.ChoiceField(choices=ReviewStatus.choices, required=False)
    review_notes = serializers.CharField(required=False, allow_blank=True)

    def validate_tags(self, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            cleaned = item.strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(cleaned[:50])
        return normalized
