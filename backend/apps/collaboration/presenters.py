from __future__ import annotations

from django.contrib.auth import get_user_model

from apps.collaboration.models import ActivityEvent, ResourceComment, ResourceShareLink, WorkspaceCollection, WorkspaceCollectionItem
from apps.collaboration.resources import resource_reference, resolve_share_link_resource
from apps.workspaces.presenters import serialize_workspace


User = get_user_model()


def _user_display(user: User | None) -> str | None:
    if user is None:
        return None
    full_name = user.get_full_name().strip()
    return full_name or user.username


def serialize_resource_comment(comment: ResourceComment) -> dict[str, object | None]:
    return {
        "id": comment.id,
        "workspace": serialize_workspace(comment.workspace),
        "author_id": comment.author_id,
        "author_display_name": _user_display(comment.author),
        "resource_kind": comment.resource_kind,
        "resource_id": comment.resource_id,
        "body": comment.body,
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),
    }


def serialize_share_link(share_link: ResourceShareLink) -> dict[str, object | None]:
    resource = resolve_share_link_resource(share_link)
    return {
        "id": share_link.id,
        "workspace": serialize_workspace(share_link.workspace),
        "created_by_id": share_link.created_by_id,
        "created_by_display_name": _user_display(share_link.created_by),
        "resource_kind": share_link.resource_kind,
        "resource_id": share_link.resource_id,
        "resource": resource_reference(share_link.resource_kind, resource),
        "label": share_link.label or None,
        "token": share_link.token,
        "share_path": f"/shared/{share_link.token}",
        "access_scope": share_link.access_scope,
        "expires_at": share_link.expires_at.isoformat() if share_link.expires_at else None,
        "revoked_at": share_link.revoked_at.isoformat() if share_link.revoked_at else None,
        "last_accessed_at": share_link.last_accessed_at.isoformat() if share_link.last_accessed_at else None,
        "is_active": share_link.is_active,
        "is_expired": share_link.is_expired,
        "created_at": share_link.created_at.isoformat(),
        "updated_at": share_link.updated_at.isoformat(),
    }


def serialize_collection_item(item: WorkspaceCollectionItem) -> dict[str, object | None]:
    resource = resolve_share_link_resource(
        ResourceShareLink(
            workspace=item.collection.workspace,
            resource_kind=item.resource_kind,
            resource_id=item.resource_id,
        )
    )
    return {
        "id": item.id,
        "resource_kind": item.resource_kind,
        "resource_id": item.resource_id,
        "resource": resource_reference(item.resource_kind, resource),
        "note": item.note,
        "position": item.position,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def serialize_collection(collection: WorkspaceCollection) -> dict[str, object | None]:
    return {
        "id": collection.id,
        "workspace": serialize_workspace(collection.workspace),
        "created_by_id": collection.created_by_id,
        "created_by_display_name": _user_display(collection.created_by),
        "name": collection.name,
        "description": collection.description,
        "is_pinned": collection.is_pinned,
        "items": [serialize_collection_item(item) for item in collection.items.all()],
        "created_at": collection.created_at.isoformat(),
        "updated_at": collection.updated_at.isoformat(),
    }


def serialize_activity_event(event: ActivityEvent) -> dict[str, object | None]:
    return {
        "id": event.id,
        "workspace": serialize_workspace(event.workspace),
        "actor_id": event.actor_id,
        "actor_display_name": _user_display(event.actor),
        "resource_kind": event.resource_kind,
        "resource_id": event.resource_id,
        "verb": event.verb,
        "summary": event.summary,
        "metadata": event.metadata,
        "created_at": event.created_at.isoformat(),
    }

