from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.workspaces.models import Workspace


class WorkspaceUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=False, max_length=255)
    timezone = serializers.CharField(required=False, allow_blank=False, max_length=64)

    def update(self, instance: Workspace, validated_data: dict[str, str]) -> Workspace:
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.full_clean(validate_unique=False)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        if validated_data:
            instance.save(update_fields=[*validated_data.keys()])
        return instance
