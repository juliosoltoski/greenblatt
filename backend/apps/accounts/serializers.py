from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.workspaces.presenters import serialize_membership


User = get_user_model()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False)


class CurrentUserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, max_length=254)

    def validate_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            return ""
        queryset = User.objects.filter(email__iexact=normalized)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return normalized

    def update(self, instance: User, validated_data: dict[str, str]) -> User:
        for field in ("first_name", "last_name", "email"):
            if field not in validated_data:
                continue
            setattr(instance, field, validated_data[field])
        try:
            instance.full_clean(validate_unique=False)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        if validated_data:
            instance.save(update_fields=[*validated_data.keys()])
        return instance


def serialize_user(user: User) -> dict[str, object | None]:
    memberships = list(user.workspace_memberships.select_related("workspace", "workspace__owner").order_by("workspace__name"))
    workspaces = [serialize_membership(membership) for membership in memberships]
    active_workspace = workspaces[0] if workspaces else None
    display_name = user.get_full_name().strip() or user.username
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "display_name": display_name,
        "is_staff": user.is_staff,
        "active_workspace": active_workspace,
        "workspaces": workspaces,
    }
