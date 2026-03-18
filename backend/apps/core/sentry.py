from __future__ import annotations

from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from apps.core.context import current_observability_context


def _before_send(event, _hint):
    context = current_observability_context()
    if not context:
        return event
    tags = dict(event.get("tags", {}))
    for key in ("request_id", "correlation_id", "job_id", "task_id", "workspace_id", "user_id"):
        value = context.get(key)
        if value:
            tags[key] = value
    event["tags"] = tags
    return event


def initialize_sentry(
    *,
    dsn: str | None,
    environment: str,
    release: str | None,
    traces_sample_rate: float,
    profiles_sample_rate: float,
    send_default_pii: bool,
) -> None:
    if not dsn:
        return
    sentry_init(
        dsn=dsn,
        environment=environment,
        release=release,
        send_default_pii=send_default_pii,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        before_send=_before_send,
    )
