from __future__ import annotations

from django.contrib.auth.models import AnonymousUser

from apps.workspaces.models import Workspace, WorkspaceMembership


ROLE_RANK = {
    WorkspaceMembership.Role.VIEWER: 0,
    WorkspaceMembership.Role.ANALYST: 1,
    WorkspaceMembership.Role.ADMIN: 2,
    WorkspaceMembership.Role.OWNER: 3,
}


def get_workspace_membership(user, workspace: Workspace) -> WorkspaceMembership | None:
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return None
    return workspace.memberships.filter(user=user).first()


def has_workspace_role(user, workspace: Workspace, minimum_role: str) -> bool:
    membership = get_workspace_membership(user, workspace)
    if membership is None:
        return False
    return ROLE_RANK[membership.role] >= ROLE_RANK[minimum_role]
