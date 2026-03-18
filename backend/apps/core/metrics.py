from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean

from django.db.models import Count
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily


HTTP_REQUEST_TOTAL = Counter(
    "greenblatt_http_requests_total",
    "HTTP requests handled by the Django API.",
    ["method", "route", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "greenblatt_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, math.inf),
)
API_THROTTLE_REJECTIONS_TOTAL = Counter(
    "greenblatt_api_throttle_rejections_total",
    "Requests rejected by DRF throttling.",
    ["scope"],
)
WORKSPACE_CONCURRENCY_REJECTIONS_TOTAL = Counter(
    "greenblatt_workspace_concurrency_rejections_total",
    "Async launches rejected by workspace concurrency limits.",
    ["job_type", "limit_name"],
)


def record_http_request(*, method: str, route: str, status_code: int, duration_seconds: float) -> None:
    normalized_route = route or "unknown"
    normalized_status = str(status_code)
    HTTP_REQUEST_TOTAL.labels(method=method, route=normalized_route, status_code=normalized_status).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=normalized_route).observe(max(0.0, duration_seconds))


def record_api_throttle_rejection(scope: str) -> None:
    API_THROTTLE_REJECTIONS_TOTAL.labels(scope=scope).inc()


def record_workspace_concurrency_rejection(*, job_type: str, limit_name: str) -> None:
    WORKSPACE_CONCURRENCY_REJECTIONS_TOTAL.labels(job_type=job_type, limit_name=limit_name).inc()


class DatabaseBackedMetricsCollector:
    def collect(self):  # pragma: no cover - exercised through endpoint tests rather than unit-level collector hooks
        from apps.automation.models import NotificationEvent
        from apps.jobs.models import JobRun

        try:
            yield from self._job_record_metrics(JobRun)
            yield from self._job_latency_metrics(JobRun)
            yield from self._provider_failure_metrics(JobRun)
            yield from self._notification_metrics(NotificationEvent)
        except Exception:
            error_metric = GaugeMetricFamily(
                "greenblatt_metrics_collector_error",
                "Whether the database-backed metrics collector encountered an error.",
            )
            error_metric.add_metric([], 1)
            yield error_metric

    @staticmethod
    def _job_record_metrics(job_model):
        persisted = GaugeMetricFamily(
            "greenblatt_job_records",
            "Persisted jobs grouped by job type and state.",
            labels=["job_type", "state"],
        )
        for row in job_model.objects.values("job_type", "state").annotate(total=Count("id")):
            persisted.add_metric([row["job_type"], row["state"]], row["total"])
        yield persisted

        active = GaugeMetricFamily(
            "greenblatt_job_active",
            "Queued or running jobs grouped by workspace and job type.",
            labels=["workspace_id", "job_type"],
        )
        for row in (
            job_model.objects.filter(state__in=[job_model.State.QUEUED, job_model.State.RUNNING])
            .values("workspace_id", "job_type")
            .annotate(total=Count("id"))
        ):
            active.add_metric([str(row["workspace_id"]), row["job_type"]], row["total"])
        yield active

    @staticmethod
    def _job_latency_metrics(job_model):
        queue_samples: dict[str, list[float]] = defaultdict(list)
        duration_samples: dict[tuple[str, str], list[float]] = defaultdict(list)
        for job in job_model.objects.exclude(started_at__isnull=True).only(
            "job_type",
            "state",
            "created_at",
            "started_at",
            "finished_at",
        ):
            queue_samples[job.job_type].append(max(0.0, (job.started_at - job.created_at).total_seconds()))
            if job.finished_at is not None:
                duration_samples[(job.job_type, job.state)].append(
                    max(0.0, (job.finished_at - job.started_at).total_seconds())
                )

        queue_avg = GaugeMetricFamily(
            "greenblatt_job_queue_latency_seconds_avg",
            "Average job queue latency in seconds.",
            labels=["job_type"],
        )
        queue_max = GaugeMetricFamily(
            "greenblatt_job_queue_latency_seconds_max",
            "Maximum job queue latency in seconds.",
            labels=["job_type"],
        )
        for job_type, samples in queue_samples.items():
            queue_avg.add_metric([job_type], mean(samples))
            queue_max.add_metric([job_type], max(samples))
        yield queue_avg
        yield queue_max

        duration_avg = GaugeMetricFamily(
            "greenblatt_job_run_duration_seconds_avg",
            "Average terminal job duration in seconds.",
            labels=["job_type", "state"],
        )
        duration_max = GaugeMetricFamily(
            "greenblatt_job_run_duration_seconds_max",
            "Maximum terminal job duration in seconds.",
            labels=["job_type", "state"],
        )
        for (job_type, state), samples in duration_samples.items():
            duration_avg.add_metric([job_type, state], mean(samples))
            duration_max.add_metric([job_type, state], max(samples))
        yield duration_avg
        yield duration_max

    @staticmethod
    def _provider_failure_metrics(job_model):
        failures = GaugeMetricFamily(
            "greenblatt_provider_failures",
            "Provider-related job failures grouped by job type, provider, and error code.",
            labels=["job_type", "provider_name", "error_code"],
        )
        counts: dict[tuple[str, str, str], int] = defaultdict(int)
        for job in job_model.objects.filter(error_code__in=["provider_failure", "provider_build_failed"]).only(
            "job_type",
            "error_code",
            "metadata",
        ):
            provider_failure = job.metadata.get("provider_failure", {})
            provider_name = str(provider_failure.get("provider_name") or "unknown")
            counts[(job.job_type, provider_name, job.error_code)] += 1
        for (job_type, provider_name, error_code), total in counts.items():
            failures.add_metric([job_type, provider_name, error_code], total)
        yield failures

    @staticmethod
    def _notification_metrics(notification_model):
        events = GaugeMetricFamily(
            "greenblatt_notification_events",
            "Persisted notification events grouped by event type and status.",
            labels=["event_type", "status"],
        )
        for row in notification_model.objects.values("event_type", "status").annotate(total=Count("id")):
            events.add_metric([row["event_type"], row["status"]], row["total"])
        yield events


try:
    REGISTRY.register(DatabaseBackedMetricsCollector())
except ValueError:  # pragma: no cover - autoreload/import duplication
    pass


def metrics_content() -> bytes:
    return generate_latest(REGISTRY)


__all__ = [
    "CONTENT_TYPE_LATEST",
    "metrics_content",
    "record_api_throttle_rejection",
    "record_http_request",
    "record_workspace_concurrency_rejection",
]
