from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

from apps.core.plans import unique_preserve_order, workspace_usage_payload
from apps.core.providers import configured_provider_health_payload, provider_config_from_request_payload
from apps.jobs.errors import ProviderBuildError, wrap_provider_runtime_error
from apps.jobs.models import JobRun
from apps.jobs.presenters import serialize_job
from apps.jobs.services import JobService
from apps.universes.models import Universe
from apps.workspaces.models import Workspace
from greenblatt.services import ProviderConfig, build_provider, provider_result_payload, serialize_provider_config


if TYPE_CHECKING:
    from apps.jobs.tasks import TrackedJobTask


PROVIDER_OPERATOR_GUIDANCE: dict[str, dict[str, object]] = {
    "yahoo": {
        "cost_tier": "free",
        "rate_limit_profile": "Unofficial provider with variable throttling.",
        "recommended_candidate_limit": 250,
        "cache_advice": "Use cache for repeated research and warm common universes before large runs.",
        "supports_cache_warm": True,
    },
    "alpha_vantage": {
        "cost_tier": "metered",
        "rate_limit_profile": f"API-key-backed service with roughly {getattr(settings, 'ALPHA_VANTAGE_MAX_CALLS_PER_MINUTE', 5)} calls per minute configured.",
        "recommended_candidate_limit": 75,
        "cache_advice": "Warm only the symbols you expect to reuse and avoid unnecessary refreshes.",
        "supports_cache_warm": True,
    },
}


@dataclass(frozen=True, slots=True)
class ProviderCacheWarmRequest:
    workspace: Workspace
    created_by: object
    universe: Universe
    sample_size: int
    refresh_cache: bool
    cache_ttl_hours: float
    provider_name: str | None = None
    fallback_provider_name: str | None = None


class ProviderCacheWarmJobService:
    def __init__(self, *, job_service: JobService | None = None, provider_factory=None) -> None:
        self.job_service = job_service or JobService()
        self.provider_factory = provider_factory or build_provider

    def launch_cache_warm(self, request: ProviderCacheWarmRequest) -> JobRun:
        provider_config = provider_config_from_request_payload(
            {
                "provider_name": request.provider_name,
                "fallback_provider_name": request.fallback_provider_name,
            },
            use_cache=True,
            refresh_cache=request.refresh_cache,
            cache_ttl_hours=request.cache_ttl_hours,
        )
        job = self.job_service.create_job(
            workspace=request.workspace,
            created_by=request.created_by,
            job_type="provider_cache_warm",
            metadata={
                "request": {
                    "universe_id": request.universe.id,
                    "sample_size": request.sample_size,
                    "refresh_cache": request.refresh_cache,
                    "cache_ttl_hours": request.cache_ttl_hours,
                    "provider": serialize_provider_config(provider_config),
                }
            },
            current_step="Queued for provider cache warm",
        )
        return self.enqueue_cache_warm_job(job)

    def enqueue_cache_warm_job(self, job: JobRun) -> JobRun:
        from apps.core.tasks import run_provider_cache_warm_job

        try:
            async_result = run_provider_cache_warm_job.apply_async(
                kwargs={"job_run_id": job.id},
                queue="default",
            )
        except Exception as exc:
            job.state = JobRun.State.FAILED
            job.error_code = "dispatch_failed"
            job.error_message = str(exc)
            job.finished_at = timezone.now()
            job.metadata = {
                **job.metadata,
                "last_error": {
                    "code": job.error_code,
                    "message": job.error_message,
                    "retryable": False,
                },
            }
            job.updated_at = timezone.now()
            job.save(update_fields=["state", "error_code", "error_message", "finished_at", "metadata", "updated_at"])
            return JobRun.objects.select_related("workspace", "created_by").get(pk=job.pk)

        JobRun.objects.filter(pk=job.pk).update(celery_task_id=async_result.id or "", updated_at=timezone.now())
        refreshed = JobRun.objects.select_related("workspace", "created_by").get(pk=job.pk)
        self.job_service.record_event(
            refreshed,
            event_type="dispatched",
            message="Provider cache-warm job dispatched to Celery.",
            metadata={"celery_task_id": async_result.id or ""},
        )
        return refreshed

    def execute_cache_warm_job(
        self,
        *,
        job_run_id: int,
        task: TrackedJobTask | None = None,
        job: JobRun | None = None,
    ) -> dict[str, object]:
        active_job = job or JobRun.objects.select_related("workspace", "created_by").get(pk=job_run_id)
        request_payload = active_job.metadata.get("request", {}) if isinstance(active_job.metadata, dict) else {}
        if not isinstance(request_payload, dict):
            request_payload = {}

        universe_id = int(request_payload.get("universe_id") or 0)
        sample_size = max(1, min(500, int(request_payload.get("sample_size") or 100)))
        universe = (
            Universe.objects.select_related("workspace", "source_upload")
            .prefetch_related("entries")
            .get(pk=universe_id, workspace=active_job.workspace)
        )
        tickers = [entry.normalized_ticker for entry in universe.entries.all()[:sample_size]]
        if not tickers:
            raise RuntimeError("The selected universe has no tickers available for cache warming.")

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=10,
                current_step=f"Preparing {len(tickers)} tickers from {universe.name}",
                metadata={"universe_id": universe.id},
            )
            active_job.refresh_from_db()

        provider_config = provider_config_from_request_payload(
            request_payload.get("provider") if isinstance(request_payload.get("provider"), dict) else None,
            use_cache=True,
            refresh_cache=bool(request_payload.get("refresh_cache", False)),
            cache_ttl_hours=float(request_payload.get("cache_ttl_hours", 24.0)),
        )
        provider_name = provider_config.provider_name
        try:
            provider = self.provider_factory(provider_config)
        except Exception as exc:
            raise ProviderBuildError(
                f"Failed to initialize market data provider '{provider_name}': {exc}",
                provider_name=provider_name,
                workflow="provider_cache_warm",
            ) from exc

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=40,
                current_step="Fetching snapshots to populate the provider cache",
            )
            active_job.refresh_from_db()

        try:
            snapshots = provider.get_snapshots(tickers, include_momentum=True)
        except Exception as exc:
            wrapped = wrap_provider_runtime_error(exc, provider_name=provider_name, workflow="provider_cache_warm")
            if wrapped is not None:
                raise wrapped from exc
            raise

        provider_info = provider_result_payload(provider, provider_config)
        anomalies = _snapshot_anomaly_payload(tickers=tickers, snapshots=snapshots)

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=90,
                current_step="Finalizing provider diagnostics",
            )

        return {
            "job_type": "provider_cache_warm",
            "universe_id": universe.id,
            "universe_name": universe.name,
            "requested_ticker_count": len(tickers),
            "warmed_ticker_count": len(snapshots),
            "provider": provider_info,
            "data_quality": anomalies,
        }


def provider_diagnostics_payload(*, workspace: Workspace, probe: bool = False) -> dict[str, object]:
    base_payload = configured_provider_health_payload(probe=probe)
    failures = _provider_failure_summary(workspace)
    recent_cache_warm_jobs = [
        serialize_job(job)
        for job in JobRun.objects.select_related("workspace", "created_by")
        .filter(workspace=workspace, job_type="provider_cache_warm")
        .order_by("-created_at")[:5]
    ]

    providers: list[dict[str, object]] = []
    for provider in base_payload["providers"]:
        provider_key = str(provider["key"])
        guidance = PROVIDER_OPERATOR_GUIDANCE.get(provider_key, {})
        failure_summary = failures.get(provider_key, _empty_failure_summary())
        providers.append(
            {
                **provider,
                "cost_tier": guidance.get("cost_tier", "unknown"),
                "rate_limit_profile": guidance.get("rate_limit_profile", "No operator guidance configured."),
                "recommended_candidate_limit": guidance.get("recommended_candidate_limit"),
                "cache_advice": guidance.get("cache_advice", "Use cached responses for repeated research."),
                "supports_cache_warm": bool(guidance.get("supports_cache_warm", True)),
                "recent_failure_count": failure_summary["count"],
                "last_failure_at": failure_summary["last_failure_at"],
                "last_failure_message": failure_summary["last_failure_message"],
                "workflows": failure_summary["workflows"],
                "throttle_events": failure_summary["throttle_events"],
            }
        )

    return {
        "workspace_id": workspace.id,
        "default_provider": base_payload["default_provider"],
        "fallback_provider": base_payload["fallback_provider"],
        "providers": providers,
        "workspace_usage": workspace_usage_payload(workspace),
        "recent_cache_warm_jobs": recent_cache_warm_jobs,
        "recommendations": _build_provider_recommendations(base_payload=base_payload, providers=providers, workspace=workspace),
    }


def _provider_failure_summary(workspace: Workspace) -> dict[str, dict[str, object]]:
    summary: dict[str, dict[str, object]] = defaultdict(_empty_failure_summary)
    jobs = (
        JobRun.objects.filter(workspace=workspace, error_code__in=["provider_failure", "provider_build_failed"])
        .order_by("-updated_at")[:100]
    )
    for job in jobs:
        metadata = job.metadata if isinstance(job.metadata, dict) else {}
        provider_failure = metadata.get("provider_failure") if isinstance(metadata.get("provider_failure"), dict) else {}
        provider_name = str(provider_failure.get("provider_name") or "unknown")
        bucket = summary[provider_name]
        bucket["count"] = int(bucket["count"]) + 1
        if bucket["last_failure_at"] is None:
            bucket["last_failure_at"] = job.updated_at.isoformat()
        if bucket["last_failure_message"] is None:
            bucket["last_failure_message"] = job.error_message or None
        workflow = str(provider_failure.get("workflow") or "").strip()
        if workflow:
            bucket["workflows"] = unique_preserve_order([*bucket["workflows"], workflow])
        if "rate" in (job.error_message or "").lower() or "throttle" in (job.error_message or "").lower():
            bucket["throttle_events"] = int(bucket["throttle_events"]) + 1
    return summary


def _empty_failure_summary() -> dict[str, object]:
    return {
        "count": 0,
        "last_failure_at": None,
        "last_failure_message": None,
        "workflows": [],
        "throttle_events": 0,
    }


def _build_provider_recommendations(
    *,
    base_payload: dict[str, object],
    providers: list[dict[str, object]],
    workspace: Workspace,
) -> list[str]:
    recommendations: list[str] = []
    fallback_provider = base_payload.get("fallback_provider")
    if fallback_provider in {None, ""}:
        recommendations.append("Configure a fallback provider before relying on scheduled automation.")
    for provider in providers:
        if int(provider["recent_failure_count"]) >= 3:
            recommendations.append(
                f"{provider['label']} has repeated recent failures in this workspace. Prefer smaller universes or warm the cache first."
            )
        if int(provider["throttle_events"]) > 0:
            recommendations.append(
                f"{provider['label']} recently showed rate-limit pressure. Keep cache enabled and avoid refresh-heavy reruns."
            )
    if not JobRun.objects.filter(workspace=workspace, job_type="provider_cache_warm").exists():
        recommendations.append("Warm a common universe before large first-run screens or backtests to reduce cold-start delays.")
    return unique_preserve_order(recommendations)


def _snapshot_anomaly_payload(*, tickers: list[str], snapshots) -> dict[str, object]:
    requested = {ticker.strip().upper() for ticker in tickers if ticker and ticker.strip()}
    returned = {str(snapshot.ticker).strip().upper() for snapshot in snapshots}
    missing = sorted(requested - returned)
    low_cap = sorted(
        str(snapshot.ticker)
        for snapshot in snapshots
        if snapshot.market_cap is not None and snapshot.market_cap < 50_000_000
    )
    missing_ebit = sorted(str(snapshot.ticker) for snapshot in snapshots if snapshot.ebit in {None, 0})
    warnings: list[dict[str, str]] = []
    if missing:
        warnings.append(
            {
                "code": "missing_snapshots",
                "severity": "warning",
                "message": f"{len(missing)} requested tickers did not return fundamentals during cache warm.",
            }
        )
    if missing_ebit:
        warnings.append(
            {
                "code": "missing_ebit",
                "severity": "notice",
                "message": f"{len(missing_ebit)} warmed tickers are missing EBIT or returned zero EBIT.",
            }
        )
    return {
        "requested_count": len(requested),
        "returned_count": len(returned),
        "missing_tickers": missing[:20],
        "low_market_cap_tickers": low_cap[:20],
        "missing_ebit_tickers": missing_ebit[:20],
        "warning_count": len(warnings),
        "warnings": warnings,
    }
