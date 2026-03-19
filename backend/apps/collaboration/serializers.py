from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from apps.collaboration.models import CollaborationResourceKind, ResourceShareLink


class PaginationSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class ResourceScopeSerializer(serializers.Serializer):
    resource_kind = serializers.ChoiceField(choices=CollaborationResourceKind.choices)
    resource_id = serializers.IntegerField(min_value=1)


class CommentListSerializer(PaginationSerializer, ResourceScopeSerializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)


class CommentCreateSerializer(ResourceScopeSerializer):
    body = serializers.CharField()

    def validate_body(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Comment body cannot be blank.")
        return cleaned


class ShareLinkListSerializer(PaginationSerializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    resource_kind = serializers.ChoiceField(choices=CollaborationResourceKind.choices, required=False)
    resource_id = serializers.IntegerField(required=False, min_value=1)
    include_inactive = serializers.BooleanField(required=False, default=False)


class ShareLinkCreateSerializer(ResourceScopeSerializer):
    label = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    access_scope = serializers.ChoiceField(
        choices=ResourceShareLink.AccessScope.choices,
        required=False,
        default=ResourceShareLink.AccessScope.TOKEN,
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiration must be in the future.")
        return value


class ShareLinkUpdateSerializer(serializers.Serializer):
    label = serializers.CharField(required=False, allow_blank=True, max_length=255)
    access_scope = serializers.ChoiceField(choices=ResourceShareLink.AccessScope.choices, required=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    is_revoked = serializers.BooleanField(required=False)

    def validate_expires_at(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("Expiration must be in the future.")
        return value


class CollectionListSerializer(PaginationSerializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)


class CollectionCreateSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    is_pinned = serializers.BooleanField(required=False, default=False)

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Collection name cannot be blank.")
        return cleaned


class CollectionUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    is_pinned = serializers.BooleanField(required=False)

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Collection name cannot be blank.")
        return cleaned


class CollectionItemCreateSerializer(ResourceScopeSerializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")
    position = serializers.IntegerField(required=False, min_value=1)


class CollectionItemUpdateSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True)
    position = serializers.IntegerField(required=False, min_value=1)


class ActivityEventListSerializer(PaginationSerializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    resource_kind = serializers.ChoiceField(choices=CollaborationResourceKind.choices, required=False)
    resource_id = serializers.IntegerField(required=False, min_value=1)

