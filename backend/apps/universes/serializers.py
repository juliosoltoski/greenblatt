from __future__ import annotations

from rest_framework import serializers

from apps.universes.models import Universe


SOURCE_FIELDS = {"source_type", "profile_key", "manual_tickers", "upload_file"}


class UniverseMutationSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    source_type = serializers.ChoiceField(choices=Universe.SourceType.choices, required=False)
    profile_key = serializers.CharField(required=False, allow_blank=False)
    manual_tickers = serializers.CharField(required=False, allow_blank=True)
    upload_file = serializers.FileField(required=False)

    def validate(self, attrs):
        instance: Universe | None = getattr(self, "instance", None)
        creating = instance is None
        source_fields_present = any(field in attrs for field in SOURCE_FIELDS)

        if creating and "name" not in attrs:
            raise serializers.ValidationError({"name": "This field is required."})
        if creating and "source_type" not in attrs:
            raise serializers.ValidationError({"source_type": "This field is required."})
        if not creating and not attrs:
            raise serializers.ValidationError({"detail": "No changes submitted."})

        if not creating and "workspace_id" in attrs:
            raise serializers.ValidationError({"workspace_id": "Workspace cannot be changed after creation."})

        resolved_source_type = attrs.get("source_type", instance.source_type if instance else None)

        if creating or source_fields_present:
            if resolved_source_type == Universe.SourceType.BUILT_IN:
                profile_key = attrs.get("profile_key", instance.profile_key if instance else None)
                if not profile_key:
                    raise serializers.ValidationError(
                        {"profile_key": "Select a built-in profile for built-in universes."}
                    )
            elif resolved_source_type == Universe.SourceType.MANUAL:
                manual_tickers = attrs.get("manual_tickers")
                if manual_tickers is None and (creating or instance is None or instance.source_type != Universe.SourceType.MANUAL):
                    raise serializers.ValidationError({"manual_tickers": "Paste one or more tickers."})
                if manual_tickers is not None and not manual_tickers.strip():
                    raise serializers.ValidationError({"manual_tickers": "Paste one or more tickers."})
            elif resolved_source_type == Universe.SourceType.UPLOADED_FILE:
                upload_file = attrs.get("upload_file")
                if upload_file is None and (creating or instance is None or instance.source_type != Universe.SourceType.UPLOADED_FILE):
                    raise serializers.ValidationError(
                        {"upload_file": "Attach a newline-delimited ticker file."}
                    )

        return attrs
