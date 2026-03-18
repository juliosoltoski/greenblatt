from __future__ import annotations

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import LaunchRateThrottle, MethodScopedThrottleMixin
from apps.backtests.models import BacktestRun
from apps.backtests.presenters import serialize_backtest_run
from apps.screens.models import ScreenRun
from apps.screens.presenters import serialize_screen_run
from apps.strategy_templates.models import StrategyTemplate
from apps.strategy_templates.presenters import serialize_strategy_template
from apps.strategy_templates.serializers import (
    StrategyTemplateCreateSerializer,
    StrategyTemplateListSerializer,
    StrategyTemplateUpdateSerializer,
)
from apps.strategy_templates.services import (
    StrategyTemplateDefinition,
    StrategyTemplateService,
    backtest_config_from_run,
    normalize_template_config,
    screen_config_from_run,
)
from apps.universes.models import Universe
from apps.workspaces.access import accessible_workspace_ids, require_workspace_role, resolve_workspace_for_request


def _paginate_queryset(queryset, *, page: int, page_size: int):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return paginator, page_obj


def _template_queryset(user):
    return (
        StrategyTemplate.objects.select_related(
            "workspace",
            "created_by",
            "universe",
            "universe__workspace",
            "universe__source_upload",
            "source_screen_run",
            "source_backtest_run",
        )
        .prefetch_related("universe__entries")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


def _screen_queryset(user):
    return (
        ScreenRun.objects.select_related("workspace", "created_by", "universe", "job", "universe__workspace", "universe__source_upload")
        .prefetch_related("universe__entries")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


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


class StrategyTemplateListCreateView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [LaunchRateThrottle],
    }

    def get(self, request):
        serializer = StrategyTemplateListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        queryset = _template_queryset(request.user).filter(workspace=workspace)
        workflow_kind = serializer.validated_data.get("workflow_kind")
        if workflow_kind:
            queryset = queryset.filter(workflow_kind=workflow_kind)
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
                "results": [serialize_strategy_template(template) for template in page_obj.object_list],
            }
        )

    def post(self, request):
        serializer = StrategyTemplateCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source_screen_run_id = serializer.validated_data.get("source_screen_run_id")
        source_backtest_run_id = serializer.validated_data.get("source_backtest_run_id")
        source_screen_run = None
        source_backtest_run = None
        universe = None
        if source_screen_run_id is not None:
            source_screen_run = get_object_or_404(_screen_queryset(request.user), pk=source_screen_run_id)
            workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id") or source_screen_run.workspace_id)
            if workspace.id != source_screen_run.workspace_id:
                return Response({"detail": "Source screen run does not belong to the requested workspace."}, status=status.HTTP_400_BAD_REQUEST)
            universe = source_screen_run.universe
            workflow_kind = StrategyTemplate.WorkflowKind.SCREEN
            config = screen_config_from_run(source_screen_run)
        elif source_backtest_run_id is not None:
            source_backtest_run = get_object_or_404(_backtest_queryset(request.user), pk=source_backtest_run_id)
            workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id") or source_backtest_run.workspace_id)
            if workspace.id != source_backtest_run.workspace_id:
                return Response({"detail": "Source backtest run does not belong to the requested workspace."}, status=status.HTTP_400_BAD_REQUEST)
            universe = source_backtest_run.universe
            workflow_kind = StrategyTemplate.WorkflowKind.BACKTEST
            config = backtest_config_from_run(source_backtest_run)
        else:
            universe = get_object_or_404(_universe_queryset(request.user), pk=serializer.validated_data["universe_id"])
            workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id") or universe.workspace_id)
            if workspace.id != universe.workspace_id:
                return Response({"detail": "Universe does not belong to the requested workspace."}, status=status.HTTP_400_BAD_REQUEST)
            workflow_kind = serializer.validated_data["workflow_kind"]
            config = normalize_template_config(workflow_kind, serializer.validated_data["config"])
        require_workspace_role(request.user, workspace, "analyst", "You need analyst access or higher to save templates.")
        template = StrategyTemplateService().create_template(
            StrategyTemplateDefinition(
                workspace=workspace,
                created_by=request.user,
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                workflow_kind=workflow_kind,
                universe=universe,
                config=config,
                source_screen_run=source_screen_run,
                source_backtest_run=source_backtest_run,
            )
        )
        return Response(serialize_strategy_template(template), status=status.HTTP_201_CREATED)


class StrategyTemplateDetailView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "PATCH": [LaunchRateThrottle],
        "DELETE": [LaunchRateThrottle],
    }

    def get(self, request, template_id: int):
        template = get_object_or_404(_template_queryset(request.user), pk=template_id)
        return Response(serialize_strategy_template(template))

    def patch(self, request, template_id: int):
        template = get_object_or_404(_template_queryset(request.user), pk=template_id)
        require_workspace_role(request.user, template.workspace, "analyst", "You need analyst access or higher to update templates.")
        serializer = StrategyTemplateUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        universe = None
        if "universe_id" in serializer.validated_data:
            universe = get_object_or_404(_universe_queryset(request.user), pk=serializer.validated_data["universe_id"])
            if universe.workspace_id != template.workspace_id:
                return Response({"detail": "Universe does not belong to the template workspace."}, status=status.HTTP_400_BAD_REQUEST)
        template = StrategyTemplateService().update_template(
            template,
            name=serializer.validated_data.get("name"),
            description=serializer.validated_data.get("description"),
            universe=universe,
            config=serializer.validated_data.get("config"),
        )
        return Response(serialize_strategy_template(template))

    def delete(self, request, template_id: int):
        template = get_object_or_404(_template_queryset(request.user), pk=template_id)
        require_workspace_role(request.user, template.workspace, "analyst", "You need analyst access or higher to delete templates.")
        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StrategyTemplateLaunchView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [LaunchRateThrottle],
    }

    def post(self, request, template_id: int):
        template = get_object_or_404(_template_queryset(request.user), pk=template_id)
        require_workspace_role(request.user, template.workspace, "analyst", "You need analyst access or higher to launch templates.")
        run = StrategyTemplateService().launch_template(template, launched_by=request.user)
        if template.workflow_kind == StrategyTemplate.WorkflowKind.SCREEN:
            response_status = status.HTTP_202_ACCEPTED if run.job.state == run.job.State.QUEUED else status.HTTP_503_SERVICE_UNAVAILABLE
            return Response({"workflow_kind": "screen", "run": serialize_screen_run(run)}, status=response_status)
        response_status = status.HTTP_202_ACCEPTED if run.job.state == run.job.State.QUEUED else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response({"workflow_kind": "backtest", "run": serialize_backtest_run(run)}, status=response_status)
