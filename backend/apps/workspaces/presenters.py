from __future__ import annotations

from apps.workspaces.models import Workspace, WorkspaceMembership


def serialize_workspace(workspace: Workspace) -> dict[str, object | None]:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "slug": workspace.slug,
        "plan_type": workspace.plan_type,
        "timezone": workspace.timezone,
        "owner_id": workspace.owner_id,
    }


def serialize_membership(membership: WorkspaceMembership) -> dict[str, object | None]:
    payload = serialize_workspace(membership.workspace)
    payload["role"] = membership.role
    payload["joined_at"] = membership.joined_at.isoformat()
    return payload
