from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from django.conf import settings

from apps.jobs.models import JobRun
from apps.workspaces.models import Workspace


ACTIVE_JOB_STATES = [JobRun.State.QUEUED, JobRun.State.RUNNING]


@dataclass(frozen=True, slots=True)
class WorkspacePlanDefinition:
    key: str
    label: str
    description: str
    seat_guidance: str
    automation_guidance: str
    feature_flags: tuple[str, ...]


PLAN_CATALOG: dict[str, WorkspacePlanDefinition] = {
    "personal": WorkspacePlanDefinition(
        key="personal",
        label="Personal",
        description="Single-team research workspace with shared platform defaults.",
        seat_guidance="Best for 1-2 active researchers.",
        automation_guidance="Suitable for light scheduled screens and backtests.",
        feature_flags=("research", "templates", "alerts", "sharing"),
    ),
    "team": WorkspacePlanDefinition(
        key="team",
        label="Team",
        description="Collaborative research workspace with review and automation workflows.",
        seat_guidance="Best for small analyst teams.",
        automation_guidance="Supports regular scheduled research and notification routing.",
        feature_flags=("research", "templates", "alerts", "sharing", "automation", "review"),
    ),
    "professional": WorkspacePlanDefinition(
        key="professional",
        label="Professional",
        description="Operator-friendly workspace intended for heavier recurring usage.",
        seat_guidance="Best for larger or more operational research teams.",
        automation_guidance="Supports heavier schedules, provider operations, and support workflows.",
        feature_flags=("research", "templates", "alerts", "sharing", "automation", "review", "provider_ops"),
    ),
}

DEFAULT_PLAN = PLAN_CATALOG["personal"]


def plan_catalog_payload() -> list[dict[str, object]]:
    return [serialize_plan_definition(definition) for definition in PLAN_CATALOG.values()]


def serialize_plan_definition(definition: WorkspacePlanDefinition) -> dict[str, object]:
    return {
        "key": definition.key,
        "label": definition.label,
        "description": definition.description,
        "seat_guidance": definition.seat_guidance,
        "automation_guidance": definition.automation_guidance,
        "feature_flags": list(definition.feature_flags),
        "enforced": False,
    }


def workspace_plan_payload(workspace: Workspace) -> dict[str, object]:
    definition = PLAN_CATALOG.get(workspace.plan_type, DEFAULT_PLAN)
    payload = serialize_plan_definition(definition)
    payload.update(
        {
            "current": True,
            "workspace_plan_type": workspace.plan_type,
        }
    )
    return payload


def workspace_usage_payload(workspace: Workspace) -> dict[str, object]:
    from apps.automation.models import AlertRule, RunSchedule
    from apps.backtests.models import BacktestRun
    from apps.screens.models import ScreenRun
    from apps.strategy_templates.models import StrategyTemplate
    from apps.universes.models import Universe

    active_jobs = workspace.jobs.filter(state__in=ACTIVE_JOB_STATES)
    failed_jobs = workspace.jobs.filter(state__in=[JobRun.State.FAILED, JobRun.State.PARTIAL_FAILED])
    provider_operation_jobs = active_jobs.filter(job_type="provider_cache_warm")

    return {
        "workspace_id": workspace.id,
        "member_count": workspace.memberships.count(),
        "active_jobs": {
            "total": active_jobs.count(),
            "research": active_jobs.filter(job_type__in=["screen_run", "backtest_run"]).count(),
            "smoke": active_jobs.filter(job_type="smoke_test").count(),
            "provider_operations": provider_operation_jobs.count(),
        },
        "limits": {
            "total_jobs": int(getattr(settings, "WORKSPACE_MAX_CONCURRENT_JOBS", 0) or 0),
            "research_jobs": int(getattr(settings, "WORKSPACE_MAX_CONCURRENT_RESEARCH_JOBS", 0) or 0),
            "smoke_jobs": int(getattr(settings, "WORKSPACE_MAX_CONCURRENT_SMOKE_JOBS", 0) or 0),
            "provider_operations": int(getattr(settings, "WORKSPACE_MAX_CONCURRENT_JOBS", 0) or 0),
            "enforced": False,
        },
        "resource_counts": {
            "universes": Universe.objects.filter(workspace=workspace).count(),
            "templates": StrategyTemplate.objects.filter(workspace=workspace).count(),
            "screens": ScreenRun.objects.filter(workspace=workspace).count(),
            "backtests": BacktestRun.objects.filter(workspace=workspace).count(),
            "schedules": RunSchedule.objects.filter(workspace=workspace).count(),
            "alerts": AlertRule.objects.filter(workspace=workspace).count(),
        },
        "recent_activity": {
            "jobs_total": workspace.jobs.count(),
            "failed_jobs_total": failed_jobs.count(),
            "provider_failures_total": workspace.jobs.filter(error_code__in=["provider_failure", "provider_build_failed"]).count(),
        },
    }


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
