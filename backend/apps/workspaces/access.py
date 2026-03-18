from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import PermissionDenied

from apps.workspaces.models import Workspace, WorkspaceMembership
from apps.workspaces.permissions import has_workspace_role


def membership_queryset(user):
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return WorkspaceMembership.objects.none()
    return user.workspace_memberships.select_related("workspace", "workspace__owner").order_by(
        "joined_at",
        "workspace__name",
        "workspace__id",
    )


def resolve_workspace_for_request(user, workspace_id: int | None = None) -> Workspace:
    memberships = membership_queryset(user)
    membership = memberships.filter(workspace_id=workspace_id).first() if workspace_id else memberships.first()
    if membership is None:
        raise PermissionDenied("You do not have access to the requested workspace.")
    return membership.workspace


def accessible_workspace_ids(user):
    return membership_queryset(user).values_list("workspace_id", flat=True)


def require_workspace_role(user, workspace: Workspace, minimum_role: str, message: str) -> None:
    if not has_workspace_role(user, workspace, minimum_role):
        raise PermissionDenied(message)
