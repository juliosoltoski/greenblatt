from __future__ import annotations

import json

from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import ExportRateThrottle, LaunchRateThrottle, MethodScopedThrottleMixin
from apps.screens.models import ScreenExclusion, ScreenResultRow, ScreenRun
from apps.screens.presenters import (
    serialize_screen_exclusion,
    serialize_screen_result_row,
    serialize_screen_run,
    serialize_screen_run_bundle,
)
from apps.screens.serializers import PagingSerializer, ScreenLaunchSerializer, ScreenRunListSerializer
from apps.screens.services import ScreenLaunchRequest, ScreenRunService
from apps.universes.models import Universe
from apps.universes.services import flatten_errors
from apps.workspaces.access import accessible_workspace_ids, require_workspace_role, resolve_workspace_for_request


ROW_SORT_FIELDS = {
    "position": "position",
    "ticker": "ticker",
    "company_name": "company_name",
    "market_cap": "market_cap",
    "return_on_capital": "return_on_capital",
    "earnings_yield": "earnings_yield",
    "momentum_6m": "momentum_6m",
    "final_score": "final_score",
}

EXCLUSION_SORT_FIELDS = {
    "ticker": "ticker",
    "reason": "reason",
}


def _screen_queryset(user):
    return (
        ScreenRun.objects.select_related("workspace", "created_by", "universe", "job", "universe__workspace", "universe__source_upload")
        .prefetch_related("universe__entries")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


def _universe_queryset(user):
    return (
        Universe.objects.select_related("workspace", "source_upload", "created_by")
        .prefetch_related("entries")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


def _paginate_queryset(queryset, *, page: int, page_size: int):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return paginator, page_obj


class ScreenListCreateView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [LaunchRateThrottle],
    }

    def get(self, request):
        serializer = ScreenRunListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        queryset = _screen_queryset(request.user).filter(workspace=workspace)
        job_state = serializer.validated_data.get("job_state")
        if job_state:
            queryset = queryset.filter(job__state=job_state)
        page_size = serializer.validated_data.get("limit") or serializer.validated_data["page_size"]
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=page_size,
        )
        return Response(
            {
                "workspace_id": workspace.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": page_size,
                "results": [serialize_screen_run(screen) for screen in page_obj.object_list],
            }
        )

    def post(self, request):
        serializer = ScreenLaunchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Screen request is invalid.", "errors": flatten_errors(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        universe = get_object_or_404(_universe_queryset(request.user), pk=serializer.validated_data["universe_id"])
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id") or universe.workspace_id)
        if universe.workspace_id != workspace.id:
            return Response(
                {"detail": "Selected universe does not belong to the requested workspace."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        require_workspace_role(
            request.user,
            workspace,
            "analyst",
            "You need analyst access or higher to launch screens.",
        )

        screen_run = ScreenRunService().launch_screen(
            ScreenLaunchRequest(
                workspace=workspace,
                created_by=request.user,
                universe=universe,
                top_n=serializer.validated_data["top_n"],
                momentum_mode=serializer.validated_data["momentum_mode"],
                sector_allowlist=serializer.validated_data.get("sector_allowlist", []),
                min_market_cap=serializer.validated_data.get("min_market_cap"),
                exclude_financials=serializer.validated_data["exclude_financials"],
                exclude_utilities=serializer.validated_data["exclude_utilities"],
                exclude_adrs=serializer.validated_data["exclude_adrs"],
                use_cache=serializer.validated_data["use_cache"],
                refresh_cache=serializer.validated_data["refresh_cache"],
                cache_ttl_hours=serializer.validated_data["cache_ttl_hours"],
                provider_name=serializer.validated_data.get("provider_name"),
                fallback_provider_name=serializer.validated_data.get("fallback_provider_name"),
            )
        )
        response_status = (
            status.HTTP_202_ACCEPTED if screen_run.job.state == screen_run.job.State.QUEUED else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(serialize_screen_run(screen_run), status=response_status)


class ScreenDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, screen_run_id: int):
        screen_run = get_object_or_404(_screen_queryset(request.user), pk=screen_run_id)
        return Response(serialize_screen_run(screen_run))


class ScreenResultRowListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, screen_run_id: int):
        screen_run = get_object_or_404(_screen_queryset(request.user), pk=screen_run_id)
        serializer = PagingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        sort_key = serializer.validated_data.get("sort") or "position"
        sort_field = ROW_SORT_FIELDS.get(sort_key, "position")
        direction = serializer.validated_data["direction"]
        order_by = f"-{sort_field}" if direction == "desc" else sort_field
        queryset = ScreenResultRow.objects.filter(screen_run=screen_run).order_by(order_by, "position", "id")
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "screen_run_id": screen_run.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "sort": sort_key,
                "direction": direction,
                "results": [serialize_screen_result_row(row) for row in page_obj.object_list],
            }
        )


class ScreenExclusionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, screen_run_id: int):
        screen_run = get_object_or_404(_screen_queryset(request.user), pk=screen_run_id)
        serializer = PagingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        sort_key = serializer.validated_data.get("sort") or "ticker"
        sort_field = EXCLUSION_SORT_FIELDS.get(sort_key, "ticker")
        direction = serializer.validated_data["direction"]
        order_by = f"-{sort_field}" if direction == "desc" else sort_field
        queryset = ScreenExclusion.objects.filter(screen_run=screen_run).order_by(order_by, "id")
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "screen_run_id": screen_run.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "sort": sort_key,
                "direction": direction,
                "results": [serialize_screen_exclusion(exclusion) for exclusion in page_obj.object_list],
            }
        )


class ScreenExportDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ExportRateThrottle]

    def get(self, request, screen_run_id: int):
        screen_run = get_object_or_404(_screen_queryset(request.user), pk=screen_run_id)
        service = ScreenRunService()
        try:
            path = service.export_path(screen_run)
        except FileNotFoundError as exc:
            raise Http404(str(exc)) from exc
        return FileResponse(path.open("rb"), as_attachment=True, filename=screen_run.export_filename or path.name)


class ScreenJsonExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ExportRateThrottle]

    def get(self, request, screen_run_id: int):
        screen_run = get_object_or_404(_screen_queryset(request.user), pk=screen_run_id)
        payload = serialize_screen_run_bundle(screen_run)
        response = HttpResponse(json.dumps(payload, sort_keys=True), content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="screen-run-{screen_run.id}.json"'
        return response
