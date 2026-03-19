from __future__ import annotations

from django.utils import timezone

from apps.collaboration.models import ActivityEvent, CollaborationResourceKind
from apps.workspaces.models import Workspace


def record_activity(
    *,
    workspace: Workspace,
    actor,
    resource_kind: str,
    resource_id: int,
    verb: str,
    summary: str,
    metadata: dict[str, object] | None = None,
) -> ActivityEvent:
    return ActivityEvent.objects.create(
        workspace=workspace,
        actor=actor,
        resource_kind=resource_kind,
        resource_id=resource_id,
        verb=verb,
        summary=summary[:255],
        metadata={
            **(metadata or {}),
            "recorded_at": timezone.now().isoformat(),
        },
    )


def resource_kind_for_instance(instance) -> str:
    model_name = instance._meta.model_name
    mapping = {
        "strategytemplate": CollaborationResourceKind.STRATEGY_TEMPLATE,
        "runschedule": CollaborationResourceKind.RUN_SCHEDULE,
        "screenrun": CollaborationResourceKind.SCREEN_RUN,
        "backtestrun": CollaborationResourceKind.BACKTEST_RUN,
    }
    return mapping[model_name]

