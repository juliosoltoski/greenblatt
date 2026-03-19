from __future__ import annotations

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.collaboration.models import ActivityEvent, ResourceComment, ResourceShareLink, WorkspaceCollection, WorkspaceCollectionItem
from apps.collaboration.presenters import serialize_activity_event, serialize_collection, serialize_resource_comment, serialize_share_link
from apps.collaboration.resources import resolve_share_link_resource, resolve_workspace_resource, serialize_shared_resource_bundle
from apps.collaboration.serializers import (
    ActivityEventListSerializer,
    CollectionCreateSerializer,
    CollectionItemCreateSerializer,
    CollectionItemUpdateSerializer,
    CollectionListSerializer,
    CollectionUpdateSerializer,
    CommentCreateSerializer,
    CommentListSerializer,
    ShareLinkCreateSerializer,
    ShareLinkListSerializer,
    ShareLinkUpdateSerializer,
)
from apps.collaboration.services import record_activity
from apps.core.throttling import MethodScopedThrottleMixin, MutationRateThrottle
from apps.workspaces.access import accessible_workspace_ids, require_workspace_role, resolve_workspace_for_request
from apps.workspaces.permissions import has_workspace_role


def _paginate_queryset(queryset, *, page: int, page_size: int):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return paginator, page_obj


def _comment_queryset(user):
    return ResourceComment.objects.select_related("workspace", "author").filter(
        workspace_id__in=accessible_workspace_ids(user)
    )


def _share_link_queryset(user):
    return ResourceShareLink.objects.select_related("workspace", "created_by").filter(
        workspace_id__in=accessible_workspace_ids(user)
    )


def _collection_queryset(user):
    return (
        WorkspaceCollection.objects.select_related("workspace", "created_by")
        .prefetch_related("items")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


def _activity_queryset(user):
    return ActivityEvent.objects.select_related("workspace", "actor").filter(
        workspace_id__in=accessible_workspace_ids(user)
    )


class CommentListCreateView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [MutationRateThrottle],
    }

    def get(self, request):
        serializer = CommentListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        resource = resolve_workspace_resource(
            request.user,
            serializer.validated_data["resource_kind"],
            serializer.validated_data["resource_id"],
        )
        workspace = resolve_workspace_for_request(
            request.user,
            serializer.validated_data.get("workspace_id") or resource.workspace_id,
        )
        if workspace.id != resource.workspace_id:
            return Response({"detail": "Requested resource does not belong to the workspace."}, status=status.HTTP_400_BAD_REQUEST)
        queryset = _comment_queryset(request.user).filter(
            workspace=workspace,
            resource_kind=serializer.validated_data["resource_kind"],
            resource_id=serializer.validated_data["resource_id"],
        )
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "workspace_id": workspace.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "results": [serialize_resource_comment(comment) for comment in page_obj.object_list],
            }
        )

    def post(self, request):
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = resolve_workspace_resource(
            request.user,
            serializer.validated_data["resource_kind"],
            serializer.validated_data["resource_id"],
        )
        require_workspace_role(request.user, resource.workspace, "viewer", "You need workspace access to comment on this resource.")
        comment = ResourceComment.objects.create(
            workspace=resource.workspace,
            author=request.user,
            resource_kind=serializer.validated_data["resource_kind"],
            resource_id=serializer.validated_data["resource_id"],
            body=serializer.validated_data["body"],
        )
        record_activity(
            workspace=resource.workspace,
            actor=request.user,
            resource_kind=comment.resource_kind,
            resource_id=comment.resource_id,
            verb="comment_created",
            summary=f"Commented on {comment.resource_kind.replace('_', ' ')} #{comment.resource_id}.",
            metadata={"comment_id": comment.id},
        )
        return Response(serialize_resource_comment(comment), status=status.HTTP_201_CREATED)


class CommentDetailView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "DELETE": [MutationRateThrottle],
    }

    def delete(self, request, comment_id: int):
        comment = get_object_or_404(_comment_queryset(request.user), pk=comment_id)
        can_delete = comment.author_id == request.user.id or has_workspace_role(request.user, comment.workspace, "admin")
        if not can_delete:
            return Response({"detail": "Only the author or a workspace admin can delete this comment."}, status=status.HTTP_403_FORBIDDEN)
        record_activity(
            workspace=comment.workspace,
            actor=request.user,
            resource_kind=comment.resource_kind,
            resource_id=comment.resource_id,
            verb="comment_deleted",
            summary=f"Deleted a comment on {comment.resource_kind.replace('_', ' ')} #{comment.resource_id}.",
            metadata={"comment_id": comment.id},
        )
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShareLinkListCreateView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [MutationRateThrottle],
        "PATCH": [MutationRateThrottle],
        "DELETE": [MutationRateThrottle],
    }

    def get(self, request):
        serializer = ShareLinkListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        queryset = _share_link_queryset(request.user).filter(workspace=workspace)
        resource_kind = serializer.validated_data.get("resource_kind")
        resource_id = serializer.validated_data.get("resource_id")
        if resource_kind:
            queryset = queryset.filter(resource_kind=resource_kind)
        if resource_id:
            queryset = queryset.filter(resource_id=resource_id)
        if not serializer.validated_data.get("include_inactive", False):
            queryset = queryset.filter(revoked_at__isnull=True)
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "workspace_id": workspace.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "results": [serialize_share_link(share_link) for share_link in page_obj.object_list],
            }
        )

    def post(self, request):
        serializer = ShareLinkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = resolve_workspace_resource(
            request.user,
            serializer.validated_data["resource_kind"],
            serializer.validated_data["resource_id"],
        )
        require_workspace_role(request.user, resource.workspace, "analyst", "You need analyst access or higher to create share links.")
        share_link = ResourceShareLink.objects.create(
            workspace=resource.workspace,
            created_by=request.user,
            resource_kind=serializer.validated_data["resource_kind"],
            resource_id=serializer.validated_data["resource_id"],
            label=serializer.validated_data.get("label", ""),
            access_scope=serializer.validated_data.get("access_scope", ResourceShareLink.AccessScope.TOKEN),
            expires_at=serializer.validated_data.get("expires_at"),
        )
        record_activity(
            workspace=resource.workspace,
            actor=request.user,
            resource_kind=share_link.resource_kind,
            resource_id=share_link.resource_id,
            verb="share_link_created",
            summary=f"Created a share link for {share_link.resource_kind.replace('_', ' ')} #{share_link.resource_id}.",
            metadata={"share_link_id": share_link.id, "access_scope": share_link.access_scope},
        )
        return Response(serialize_share_link(share_link), status=status.HTTP_201_CREATED)


class ShareLinkDetailView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "PATCH": [MutationRateThrottle],
        "DELETE": [MutationRateThrottle],
    }

    def patch(self, request, share_link_id: int):
        share_link = get_object_or_404(_share_link_queryset(request.user), pk=share_link_id)
        require_workspace_role(request.user, share_link.workspace, "analyst", "You need analyst access or higher to manage share links.")
        serializer = ShareLinkUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "label" in serializer.validated_data:
            share_link.label = serializer.validated_data["label"].strip()
        if "access_scope" in serializer.validated_data:
            share_link.access_scope = serializer.validated_data["access_scope"]
        if "expires_at" in serializer.validated_data:
            share_link.expires_at = serializer.validated_data["expires_at"]
        if serializer.validated_data.get("is_revoked") is True and share_link.revoked_at is None:
            share_link.revoked_at = timezone.now()
        share_link.save()
        record_activity(
            workspace=share_link.workspace,
            actor=request.user,
            resource_kind=share_link.resource_kind,
            resource_id=share_link.resource_id,
            verb="share_link_updated",
            summary=f"Updated a share link for {share_link.resource_kind.replace('_', ' ')} #{share_link.resource_id}.",
            metadata={"share_link_id": share_link.id},
        )
        return Response(serialize_share_link(share_link))

    def delete(self, request, share_link_id: int):
        share_link = get_object_or_404(_share_link_queryset(request.user), pk=share_link_id)
        require_workspace_role(request.user, share_link.workspace, "analyst", "You need analyst access or higher to revoke share links.")
        if share_link.revoked_at is None:
            share_link.revoked_at = timezone.now()
            share_link.save(update_fields=["revoked_at", "updated_at"])
            record_activity(
                workspace=share_link.workspace,
                actor=request.user,
                resource_kind=share_link.resource_kind,
                resource_id=share_link.resource_id,
                verb="share_link_revoked",
                summary=f"Revoked a share link for {share_link.resource_kind.replace('_', ' ')} #{share_link.resource_id}.",
                metadata={"share_link_id": share_link.id},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class SharedResourceView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [permissions.AllowAny]

    def get(self, request, token: str):
        share_link = get_object_or_404(
            ResourceShareLink.objects.select_related("workspace", "created_by"),
            token=token,
        )
        if not share_link.is_active:
            return Response({"detail": "This share link is no longer active."}, status=status.HTTP_404_NOT_FOUND)
        if share_link.access_scope == ResourceShareLink.AccessScope.WORKSPACE_MEMBER:
            if not request.user.is_authenticated or share_link.workspace_id not in set(accessible_workspace_ids(request.user)):
                return Response({"detail": "This share link is limited to workspace members."}, status=status.HTTP_403_FORBIDDEN)
        resource = resolve_share_link_resource(share_link)
        share_link.last_accessed_at = timezone.now()
        share_link.save(update_fields=["last_accessed_at", "updated_at"])
        return Response(
            {
                "share_link": serialize_share_link(share_link),
                "shared_resource": serialize_shared_resource_bundle(share_link),
                "workspace_name": resource.workspace.name,
            }
        )


class CollectionListCreateView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [MutationRateThrottle],
    }

    def get(self, request):
        serializer = CollectionListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        queryset = _collection_queryset(request.user).filter(workspace=workspace)
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "workspace_id": workspace.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "results": [serialize_collection(collection) for collection in page_obj.object_list],
            }
        )

    def post(self, request):
        serializer = CollectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        require_workspace_role(request.user, workspace, "analyst", "You need analyst access or higher to manage collections.")
        collection = WorkspaceCollection.objects.create(
            workspace=workspace,
            created_by=request.user,
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
            is_pinned=serializer.validated_data.get("is_pinned", False),
        )
        record_activity(
            workspace=workspace,
            actor=request.user,
            resource_kind="strategy_template",
            resource_id=collection.id,
            verb="collection_created",
            summary=f"Created collection '{collection.name}'.",
            metadata={"collection_id": collection.id},
        )
        return Response(serialize_collection(collection), status=status.HTTP_201_CREATED)


class CollectionDetailView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "PATCH": [MutationRateThrottle],
        "DELETE": [MutationRateThrottle],
    }

    def get(self, request, collection_id: int):
        collection = get_object_or_404(_collection_queryset(request.user), pk=collection_id)
        return Response(serialize_collection(collection))

    def patch(self, request, collection_id: int):
        collection = get_object_or_404(_collection_queryset(request.user), pk=collection_id)
        require_workspace_role(request.user, collection.workspace, "analyst", "You need analyst access or higher to manage collections.")
        serializer = CollectionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "name" in serializer.validated_data:
            collection.name = serializer.validated_data["name"]
        if "description" in serializer.validated_data:
            collection.description = serializer.validated_data["description"]
        if "is_pinned" in serializer.validated_data:
            collection.is_pinned = serializer.validated_data["is_pinned"]
        collection.save()
        record_activity(
            workspace=collection.workspace,
            actor=request.user,
            resource_kind="strategy_template",
            resource_id=collection.id,
            verb="collection_updated",
            summary=f"Updated collection '{collection.name}'.",
            metadata={"collection_id": collection.id},
        )
        return Response(serialize_collection(collection))

    def delete(self, request, collection_id: int):
        collection = get_object_or_404(_collection_queryset(request.user), pk=collection_id)
        require_workspace_role(request.user, collection.workspace, "analyst", "You need analyst access or higher to manage collections.")
        record_activity(
            workspace=collection.workspace,
            actor=request.user,
            resource_kind="strategy_template",
            resource_id=collection.id,
            verb="collection_deleted",
            summary=f"Deleted collection '{collection.name}'.",
            metadata={"collection_id": collection.id},
        )
        collection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CollectionItemCreateView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [MutationRateThrottle],
    }

    def post(self, request, collection_id: int):
        collection = get_object_or_404(_collection_queryset(request.user), pk=collection_id)
        require_workspace_role(request.user, collection.workspace, "analyst", "You need analyst access or higher to manage collections.")
        serializer = CollectionItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = resolve_workspace_resource(
            request.user,
            serializer.validated_data["resource_kind"],
            serializer.validated_data["resource_id"],
        )
        if resource.workspace_id != collection.workspace_id:
            return Response({"detail": "Resource does not belong to the collection workspace."}, status=status.HTTP_400_BAD_REQUEST)
        next_position = serializer.validated_data.get("position") or (collection.items.count() + 1)
        item = WorkspaceCollectionItem.objects.create(
            collection=collection,
            resource_kind=serializer.validated_data["resource_kind"],
            resource_id=serializer.validated_data["resource_id"],
            note=serializer.validated_data.get("note", ""),
            position=next_position,
        )
        record_activity(
            workspace=collection.workspace,
            actor=request.user,
            resource_kind=item.resource_kind,
            resource_id=item.resource_id,
            verb="collection_item_added",
            summary=f"Added {item.resource_kind.replace('_', ' ')} #{item.resource_id} to '{collection.name}'.",
            metadata={"collection_id": collection.id, "collection_item_id": item.id},
        )
        collection.refresh_from_db()
        return Response(serialize_collection(collection), status=status.HTTP_201_CREATED)


class CollectionItemDetailView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "PATCH": [MutationRateThrottle],
        "DELETE": [MutationRateThrottle],
    }

    def patch(self, request, collection_id: int, item_id: int):
        collection = get_object_or_404(_collection_queryset(request.user), pk=collection_id)
        require_workspace_role(request.user, collection.workspace, "analyst", "You need analyst access or higher to manage collections.")
        item = get_object_or_404(collection.items.all(), pk=item_id)
        serializer = CollectionItemUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "note" in serializer.validated_data:
            item.note = serializer.validated_data["note"]
        if "position" in serializer.validated_data:
            item.position = serializer.validated_data["position"]
        item.save()
        record_activity(
            workspace=collection.workspace,
            actor=request.user,
            resource_kind=item.resource_kind,
            resource_id=item.resource_id,
            verb="collection_item_updated",
            summary=f"Updated a collection item in '{collection.name}'.",
            metadata={"collection_id": collection.id, "collection_item_id": item.id},
        )
        collection.refresh_from_db()
        return Response(serialize_collection(collection))

    def delete(self, request, collection_id: int, item_id: int):
        collection = get_object_or_404(_collection_queryset(request.user), pk=collection_id)
        require_workspace_role(request.user, collection.workspace, "analyst", "You need analyst access or higher to manage collections.")
        item = get_object_or_404(collection.items.all(), pk=item_id)
        record_activity(
            workspace=collection.workspace,
            actor=request.user,
            resource_kind=item.resource_kind,
            resource_id=item.resource_id,
            verb="collection_item_deleted",
            summary=f"Removed {item.resource_kind.replace('_', ' ')} #{item.resource_id} from '{collection.name}'.",
            metadata={"collection_id": collection.id, "collection_item_id": item.id},
        )
        item.delete()
        collection.refresh_from_db()
        return Response(serialize_collection(collection))


class ActivityEventListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = ActivityEventListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        queryset = _activity_queryset(request.user).filter(workspace=workspace)
        if serializer.validated_data.get("resource_kind"):
            queryset = queryset.filter(resource_kind=serializer.validated_data["resource_kind"])
        if serializer.validated_data.get("resource_id"):
            queryset = queryset.filter(resource_id=serializer.validated_data["resource_id"])
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "workspace_id": workspace.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "results": [serialize_activity_event(event) for event in page_obj.object_list],
            }
        )
