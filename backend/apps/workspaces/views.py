from __future__ import annotations

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.presenters import serialize_membership


class WorkspaceListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        memberships = request.user.workspace_memberships.select_related("workspace", "workspace__owner").order_by("workspace__name")
        return Response({"results": [serialize_membership(membership) for membership in memberships]})
