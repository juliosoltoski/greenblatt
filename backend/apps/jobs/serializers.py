from __future__ import annotations

from rest_framework import serializers


class SmokeJobLaunchSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False)
    step_count = serializers.IntegerField(min_value=1, max_value=8, default=4)
    step_delay_ms = serializers.IntegerField(min_value=0, max_value=5_000, default=750)
    failure_mode = serializers.ChoiceField(choices=["success", "fail", "retry_once"], default="success")


class JobEventListSerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, default=100, min_value=1, max_value=500)
