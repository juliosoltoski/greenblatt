from __future__ import annotations

import json

from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import ExportRateThrottle, LaunchRateThrottle, MethodScopedThrottleMixin
from apps.backtests.models import BacktestFinalHolding, BacktestReviewTarget, BacktestRun, BacktestTrade
from apps.backtests.presenters import (
    serialize_backtest_equity_point,
    serialize_backtest_final_holding,
    serialize_backtest_review_target,
    serialize_backtest_run,
    serialize_backtest_run_bundle,
    serialize_backtest_trade,
)
from apps.backtests.serializers import BacktestLaunchSerializer, BacktestRunListSerializer, PagingSerializer
from apps.backtests.services import BacktestLaunchRequest, BacktestRunService
from apps.universes.models import Universe
from apps.universes.services import flatten_errors
from apps.workspaces.access import accessible_workspace_ids, require_workspace_role, resolve_workspace_for_request


TRADE_SORT_FIELDS = {
    "position": "position",
    "date": "date",
    "ticker": "ticker",
    "side": "side",
    "shares": "shares",
    "price": "price",
    "proceeds": "proceeds",
}

REVIEW_TARGET_SORT_FIELDS = {
    "position": "position",
    "date": "date",
    "target_rank": "target_rank",
    "ticker": "ticker",
    "final_score": "final_score",
}

FINAL_HOLDING_SORT_FIELDS = {
    "position": "position",
    "ticker": "ticker",
    "shares": "shares",
    "entry_date": "entry_date",
    "entry_price": "entry_price",
    "score": "score",
}


def _backtest_queryset(user):
    return (
        BacktestRun.objects.select_related(
            "workspace",
            "created_by",
            "universe",
            "job",
            "universe__workspace",
            "universe__source_upload",
        )
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


class BacktestListCreateView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [LaunchRateThrottle],
    }

    def get(self, request):
        serializer = BacktestRunListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        queryset = _backtest_queryset(request.user).filter(workspace=workspace)
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
                "results": [serialize_backtest_run(backtest) for backtest in page_obj.object_list],
            }
        )

    def post(self, request):
        serializer = BacktestLaunchSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Backtest request is invalid.", "errors": flatten_errors(serializer.errors)},
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
            "You need analyst access or higher to launch backtests.",
        )

        backtest_run = BacktestRunService().launch_backtest(
            BacktestLaunchRequest(
                workspace=workspace,
                created_by=request.user,
                universe=universe,
                start_date=serializer.validated_data["start_date"],
                end_date=serializer.validated_data["end_date"],
                initial_capital=serializer.validated_data["initial_capital"],
                portfolio_size=serializer.validated_data["portfolio_size"],
                review_frequency=serializer.validated_data["review_frequency"],
                benchmark=serializer.validated_data["benchmark"],
                momentum_mode=serializer.validated_data["momentum_mode"],
                sector_allowlist=serializer.validated_data.get("sector_allowlist", []),
                min_market_cap=serializer.validated_data.get("min_market_cap"),
                use_cache=serializer.validated_data["use_cache"],
                refresh_cache=serializer.validated_data["refresh_cache"],
                cache_ttl_hours=serializer.validated_data["cache_ttl_hours"],
                provider_name=serializer.validated_data.get("provider_name"),
                fallback_provider_name=serializer.validated_data.get("fallback_provider_name"),
            )
        )
        response_status = (
            status.HTTP_202_ACCEPTED if backtest_run.job.state == backtest_run.job.State.QUEUED else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(serialize_backtest_run(backtest_run), status=response_status)


class BacktestDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, backtest_run_id: int):
        backtest_run = get_object_or_404(_backtest_queryset(request.user), pk=backtest_run_id)
        return Response(serialize_backtest_run(backtest_run))


class BacktestEquityPointListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, backtest_run_id: int):
        backtest_run = get_object_or_404(_backtest_queryset(request.user), pk=backtest_run_id)
        points = backtest_run.equity_points.all().order_by("position", "id")
        return Response(
            {
                "backtest_run_id": backtest_run.id,
                "count": points.count(),
                "results": [serialize_backtest_equity_point(point) for point in points],
            }
        )


class BacktestTradeListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, backtest_run_id: int):
        backtest_run = get_object_or_404(_backtest_queryset(request.user), pk=backtest_run_id)
        serializer = PagingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        sort_key = serializer.validated_data.get("sort") or "position"
        sort_field = TRADE_SORT_FIELDS.get(sort_key, "position")
        direction = serializer.validated_data["direction"]
        order_by = f"-{sort_field}" if direction == "desc" else sort_field
        queryset = BacktestTrade.objects.filter(backtest_run=backtest_run).order_by(order_by, "position", "id")
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "backtest_run_id": backtest_run.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "sort": sort_key,
                "direction": direction,
                "results": [serialize_backtest_trade(trade) for trade in page_obj.object_list],
            }
        )


class BacktestReviewTargetListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, backtest_run_id: int):
        backtest_run = get_object_or_404(_backtest_queryset(request.user), pk=backtest_run_id)
        serializer = PagingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        sort_key = serializer.validated_data.get("sort") or "position"
        sort_field = REVIEW_TARGET_SORT_FIELDS.get(sort_key, "position")
        direction = serializer.validated_data["direction"]
        order_by = f"-{sort_field}" if direction == "desc" else sort_field
        queryset = BacktestReviewTarget.objects.filter(backtest_run=backtest_run).order_by(order_by, "position", "id")
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "backtest_run_id": backtest_run.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "sort": sort_key,
                "direction": direction,
                "results": [serialize_backtest_review_target(target) for target in page_obj.object_list],
            }
        )


class BacktestFinalHoldingListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, backtest_run_id: int):
        backtest_run = get_object_or_404(_backtest_queryset(request.user), pk=backtest_run_id)
        serializer = PagingSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        sort_key = serializer.validated_data.get("sort") or "position"
        sort_field = FINAL_HOLDING_SORT_FIELDS.get(sort_key, "position")
        direction = serializer.validated_data["direction"]
        order_by = f"-{sort_field}" if direction == "desc" else sort_field
        queryset = BacktestFinalHolding.objects.filter(backtest_run=backtest_run).order_by(order_by, "position", "id")
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "backtest_run_id": backtest_run.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "sort": sort_key,
                "direction": direction,
                "results": [serialize_backtest_final_holding(holding) for holding in page_obj.object_list],
            }
        )


class BacktestExportDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ExportRateThrottle]

    def get(self, request, backtest_run_id: int):
        backtest_run = get_object_or_404(_backtest_queryset(request.user), pk=backtest_run_id)
        service = BacktestRunService()
        try:
            path = service.export_path(backtest_run)
        except FileNotFoundError as exc:
            raise Http404(str(exc)) from exc
        return FileResponse(path.open("rb"), as_attachment=True, filename=backtest_run.export_filename or path.name)


class BacktestJsonExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ExportRateThrottle]

    def get(self, request, backtest_run_id: int):
        backtest_run = get_object_or_404(_backtest_queryset(request.user), pk=backtest_run_id)
        payload = serialize_backtest_run_bundle(backtest_run)
        response = HttpResponse(json.dumps(payload, sort_keys=True), content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="backtest-run-{backtest_run.id}.json"'
        return response
