from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.workspaces.presenters import serialize_membership


User = get_user_model()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False)


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
