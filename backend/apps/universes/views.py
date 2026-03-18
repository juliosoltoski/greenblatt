from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import parsers, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.universes.models import Universe
from apps.universes.presenters import serialize_universe
from apps.universes.serializers import SOURCE_FIELDS, UniverseMutationSerializer
from apps.universes.services import UniverseInputError, UniverseManagerService, flatten_errors, list_builtin_profile_payloads
from apps.workspaces.access import accessible_workspace_ids, require_workspace_role, resolve_workspace_for_request


def _universe_queryset(user):
    return (
        Universe.objects.select_related("workspace", "source_upload", "created_by")
        .prefetch_related("entries")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class UniverseProfileListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({"results": list_builtin_profile_payloads()})


class UniverseListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.JSONParser, parsers.FormParser, parsers.MultiPartParser]

    def get(self, request):
        workspace_id = request.query_params.get("workspace_id")
        workspace = resolve_workspace_for_request(request.user, int(workspace_id) if workspace_id else None)
        universes = _universe_queryset(request.user).filter(workspace=workspace)
        if _is_truthy(request.query_params.get("starred_only")):
            universes = universes.filter(is_starred=True)
        return Response(
            {
                "workspace_id": workspace.id,
                "results": [serialize_universe(universe) for universe in universes],
            }
        )

    def post(self, request):
        serializer = UniverseMutationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Universe request is invalid.", "errors": flatten_errors(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        workspace = resolve_workspace_for_request(
            request.user,
            serializer.validated_data.get("workspace_id"),
        )
        require_workspace_role(
            request.user,
            workspace,
            "analyst",
            "You need analyst access or higher to modify universes.",
        )

        try:
            universe = UniverseManagerService().create_universe(
                workspace=workspace,
                created_by=request.user,
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                source_type=serializer.validated_data["source_type"],
                profile_key=serializer.validated_data.get("profile_key"),
                manual_tickers=serializer.validated_data.get("manual_tickers"),
                upload_file=serializer.validated_data.get("upload_file"),
                provider_name=serializer.validated_data.get("provider_name"),
                fallback_provider_name=serializer.validated_data.get("fallback_provider_name"),
            )
        except UniverseInputError as exc:
            return Response(
                {"detail": exc.detail, "errors": exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        universe = _universe_queryset(request.user).get(pk=universe.pk)
        return Response(serialize_universe(universe, include_entries=True), status=status.HTTP_201_CREATED)


class UniverseDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.JSONParser, parsers.FormParser, parsers.MultiPartParser]

    def get(self, request, universe_id: int):
        universe = get_object_or_404(_universe_queryset(request.user), pk=universe_id)
        return Response(serialize_universe(universe, include_entries=True))

    def patch(self, request, universe_id: int):
        universe = get_object_or_404(_universe_queryset(request.user), pk=universe_id)
        require_workspace_role(
            request.user,
            universe.workspace,
            "analyst",
            "You need analyst access or higher to modify universes.",
        )

        serializer = UniverseMutationSerializer(instance=universe, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"detail": "Universe request is invalid.", "errors": flatten_errors(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source_changed = any(field in serializer.validated_data for field in SOURCE_FIELDS if field != "source_type")
        if serializer.validated_data.get("source_type") and serializer.validated_data["source_type"] != universe.source_type:
            source_changed = True

        try:
            updated = UniverseManagerService().update_universe(
                universe=universe,
                updated_by=request.user,
                name=serializer.validated_data.get("name"),
                description=serializer.validated_data.get("description"),
                source_type=serializer.validated_data.get("source_type"),
                profile_key=serializer.validated_data.get("profile_key"),
                manual_tickers=serializer.validated_data.get("manual_tickers"),
                upload_file=serializer.validated_data.get("upload_file"),
                is_starred=serializer.validated_data.get("is_starred"),
                tags=serializer.validated_data.get("tags"),
                notes=serializer.validated_data.get("notes"),
                provider_name=serializer.validated_data.get("provider_name"),
                fallback_provider_name=serializer.validated_data.get("fallback_provider_name"),
                source_changed=source_changed,
            )
        except UniverseInputError as exc:
            return Response(
                {"detail": exc.detail, "errors": exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = _universe_queryset(request.user).get(pk=updated.pk)
        return Response(serialize_universe(updated, include_entries=True))

    def delete(self, request, universe_id: int):
        universe = get_object_or_404(_universe_queryset(request.user), pk=universe_id)
        require_workspace_role(
            request.user,
            universe.workspace,
            "analyst",
            "You need analyst access or higher to modify universes.",
        )
        universe.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
