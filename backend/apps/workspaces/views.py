from __future__ import annotations

from rest_framework import permissions
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.access import membership_queryset, require_workspace_role
from apps.workspaces.presenters import serialize_membership
from apps.workspaces.serializers import WorkspaceUpdateSerializer


class WorkspaceListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        memberships = request.user.workspace_memberships.select_related("workspace", "workspace__owner").order_by("workspace__name")
        return Response({"results": [serialize_membership(membership) for membership in memberships]})


class WorkspaceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, workspace_id: int):
        membership = get_object_or_404(membership_queryset(request.user), workspace_id=workspace_id)
        require_workspace_role(
            request.user,
            membership.workspace,
            "admin",
            "You need admin access or higher to update workspace settings.",
        )
        serializer = WorkspaceUpdateSerializer(instance=membership.workspace, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save()
        membership.refresh_from_db()
        return Response(serialize_membership(membership))
