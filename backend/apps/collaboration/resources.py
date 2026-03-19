from __future__ import annotations

from django.http import Http404

from apps.automation.models import RunSchedule
from apps.backtests.models import BacktestRun
from apps.collaboration.models import CollaborationResourceKind, ResourceShareLink
from apps.screens.models import ScreenRun
from apps.strategy_templates.models import StrategyTemplate
from apps.workspaces.access import accessible_workspace_ids


def _strategy_template_queryset():
    return StrategyTemplate.objects.select_related(
        "workspace",
        "created_by",
        "reviewed_by",
        "universe",
        "universe__workspace",
        "universe__source_upload",
        "source_screen_run",
        "source_backtest_run",
    ).prefetch_related("universe__entries")


def _run_schedule_queryset():
    return RunSchedule.objects.select_related(
        "workspace",
        "created_by",
        "reviewed_by",
        "strategy_template",
        "strategy_template__workspace",
        "strategy_template__created_by",
        "strategy_template__reviewed_by",
        "strategy_template__universe",
        "strategy_template__universe__workspace",
        "strategy_template__universe__source_upload",
        "periodic_task",
    ).prefetch_related("strategy_template__universe__entries")


def _screen_run_queryset():
    return ScreenRun.objects.select_related(
        "workspace",
        "created_by",
        "source_template",
        "universe",
        "job",
        "universe__workspace",
        "universe__source_upload",
    ).prefetch_related("universe__entries", "result_rows", "exclusions")


def _backtest_run_queryset():
    return BacktestRun.objects.select_related(
        "workspace",
        "created_by",
        "source_template",
        "universe",
        "job",
        "universe__workspace",
        "universe__source_upload",
    ).prefetch_related("universe__entries", "equity_points", "trades", "review_targets", "final_holdings")


def resource_queryset(resource_kind: str):
    if resource_kind == CollaborationResourceKind.STRATEGY_TEMPLATE:
        return _strategy_template_queryset()
    if resource_kind == CollaborationResourceKind.RUN_SCHEDULE:
        return _run_schedule_queryset()
    if resource_kind == CollaborationResourceKind.SCREEN_RUN:
        return _screen_run_queryset()
    if resource_kind == CollaborationResourceKind.BACKTEST_RUN:
        return _backtest_run_queryset()
    raise Http404("Unsupported resource kind.")


def resolve_workspace_resource(user, resource_kind: str, resource_id: int):
    queryset = resource_queryset(resource_kind).filter(workspace_id__in=accessible_workspace_ids(user))
    resource = queryset.filter(pk=resource_id).first()
    if resource is None:
        raise Http404("Requested resource was not found.")
    return resource


def resolve_share_link_resource(share_link: ResourceShareLink):
    resource = resource_queryset(share_link.resource_kind).filter(
        workspace_id=share_link.workspace_id,
        pk=share_link.resource_id,
    ).first()
    if resource is None:
        raise Http404("The shared resource is no longer available.")
    return resource


def resource_reference(resource_kind: str, resource) -> dict[str, object | None]:
    if resource_kind == CollaborationResourceKind.STRATEGY_TEMPLATE:
        return {
            "kind": resource_kind,
            "id": resource.id,
            "title": resource.name,
            "subtitle": f"{resource.workflow_kind.title()} · {resource.universe.name}",
            "href": f"/app/templates/{resource.id}",
            "badge": resource.review_status,
        }
    if resource_kind == CollaborationResourceKind.RUN_SCHEDULE:
        return {
            "kind": resource_kind,
            "id": resource.id,
            "title": resource.name,
            "subtitle": f"Schedule · {resource.strategy_template.name}",
            "href": "/app/schedules",
            "badge": resource.review_status,
        }
    if resource_kind == CollaborationResourceKind.SCREEN_RUN:
        return {
            "kind": resource_kind,
            "id": resource.id,
            "title": f"Screen run #{resource.id}",
            "subtitle": resource.universe.name,
            "href": f"/app/screens/{resource.id}",
            "badge": resource.job.state,
        }
    if resource_kind == CollaborationResourceKind.BACKTEST_RUN:
        return {
            "kind": resource_kind,
            "id": resource.id,
            "title": f"Backtest run #{resource.id}",
            "subtitle": f"{resource.universe.name} · {resource.start_date} to {resource.end_date}",
            "href": f"/app/backtests/{resource.id}",
            "badge": resource.job.state,
        }
    raise Http404("Unsupported resource kind.")


def serialize_shared_resource_bundle(share_link: ResourceShareLink) -> dict[str, object]:
    resource = resolve_share_link_resource(share_link)
    reference = resource_reference(share_link.resource_kind, resource)
    if share_link.resource_kind == CollaborationResourceKind.STRATEGY_TEMPLATE:
        from apps.strategy_templates.presenters import serialize_strategy_template

        payload = serialize_strategy_template(resource)
    elif share_link.resource_kind == CollaborationResourceKind.RUN_SCHEDULE:
        from apps.automation.presenters import serialize_run_schedule

        payload = serialize_run_schedule(resource)
    elif share_link.resource_kind == CollaborationResourceKind.SCREEN_RUN:
        from apps.screens.presenters import serialize_screen_run_bundle

        payload = serialize_screen_run_bundle(
            resource,
            result_rows=list(resource.result_rows.all()[:25]),
            exclusions=list(resource.exclusions.all()[:25]),
        )
    elif share_link.resource_kind == CollaborationResourceKind.BACKTEST_RUN:
        from apps.backtests.presenters import serialize_backtest_run_bundle

        payload = serialize_backtest_run_bundle(
            resource,
            equity_points=list(resource.equity_points.all()[:120]),
            trades=list(resource.trades.all()[:25]),
            review_targets=list(resource.review_targets.all()[:25]),
            final_holdings=list(resource.final_holdings.all()[:25]),
        )
    else:
        raise Http404("Unsupported resource kind.")
    return {
        "resource_kind": share_link.resource_kind,
        "reference": reference,
        "payload": payload,
    }
