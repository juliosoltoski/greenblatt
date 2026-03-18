from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.core.providers import provider_config_from_request_payload
from apps.jobs.errors import ProviderBuildError, wrap_provider_runtime_error
from apps.jobs.models import JobRun
from apps.jobs.services import JobService
from apps.screens.models import ScreenExclusion, ScreenResultRow, ScreenRun
from apps.universes.models import Universe
from apps.universes.services import ArtifactStorage
from apps.workspaces.models import Workspace
from greenblatt.models import ScreenConfig
from greenblatt.services import (
    ProviderConfig,
    ScreenRequest as CoreScreenRequest,
    ScreenService as CoreScreenService,
    UniverseRequest,
    build_provider,
    provider_result_payload,
    serialize_provider_config,
)


if TYPE_CHECKING:
    from apps.jobs.tasks import TrackedJobTask


@dataclass(frozen=True, slots=True)
class ScreenLaunchRequest:
    workspace: Workspace
    created_by: object
    universe: Universe
    top_n: int
    momentum_mode: str
    sector_allowlist: list[str]
    min_market_cap: float | None
    exclude_financials: bool
    exclude_utilities: bool
    exclude_adrs: bool
    use_cache: bool
    refresh_cache: bool
    cache_ttl_hours: float
    provider_name: str | None = None
    fallback_provider_name: str | None = None


class ScreenRunService:
    def __init__(
        self,
        *,
        job_service: JobService | None = None,
        artifact_storage: ArtifactStorage | None = None,
        provider_factory=None,
        core_screen_service_class=None,
    ) -> None:
        self.job_service = job_service or JobService()
        self.artifact_storage = artifact_storage or ArtifactStorage()
        self.provider_factory = provider_factory or build_provider
        self.core_screen_service_class = core_screen_service_class or CoreScreenService

    def launch_screen(self, request: ScreenLaunchRequest) -> ScreenRun:
        provider_config = provider_config_from_request_payload(
            {
                "provider_name": request.provider_name,
                "fallback_provider_name": request.fallback_provider_name,
            },
            use_cache=request.use_cache,
            refresh_cache=request.refresh_cache,
            cache_ttl_hours=request.cache_ttl_hours,
        )
        with transaction.atomic():
            job = self.job_service.create_job(
                workspace=request.workspace,
                created_by=request.created_by,
                job_type="screen_run",
                metadata={
                    "request": {
                        "universe_id": request.universe.id,
                        "top_n": request.top_n,
                        "momentum_mode": request.momentum_mode,
                        "sector_allowlist": request.sector_allowlist,
                        "min_market_cap": request.min_market_cap,
                        "exclude_financials": request.exclude_financials,
                        "exclude_utilities": request.exclude_utilities,
                        "exclude_adrs": request.exclude_adrs,
                        "use_cache": request.use_cache,
                        "refresh_cache": request.refresh_cache,
                        "cache_ttl_hours": request.cache_ttl_hours,
                        "provider": serialize_provider_config(provider_config),
                    }
                },
                current_step="Queued for screening",
            )
            screen_run = ScreenRun.objects.create(
                workspace=request.workspace,
                created_by=request.created_by,
                universe=request.universe,
                job=job,
                top_n=request.top_n,
                momentum_mode=request.momentum_mode,
                sector_allowlist=request.sector_allowlist,
                min_market_cap=request.min_market_cap,
                exclude_financials=request.exclude_financials,
                exclude_utilities=request.exclude_utilities,
                exclude_adrs=request.exclude_adrs,
                use_cache=request.use_cache,
                refresh_cache=request.refresh_cache,
                cache_ttl_hours=request.cache_ttl_hours,
            )
            job.metadata = {
                **job.metadata,
                "screen_run_id": screen_run.id,
            }
            job.updated_at = timezone.now()
            job.save(update_fields=["metadata", "updated_at"])

        return self.enqueue_screen(screen_run)

    def enqueue_screen(self, screen_run: ScreenRun) -> ScreenRun:
        from apps.screens.tasks import run_screen_job

        try:
            async_result = run_screen_job.apply_async(
                kwargs={
                    "job_run_id": screen_run.job_id,
                    "screen_run_id": screen_run.id,
                },
                queue="default",
            )
        except Exception as exc:
            job = screen_run.job
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
            return self.get_screen_run(screen_run.id)

        JobRun.objects.filter(pk=screen_run.job_id).update(celery_task_id=async_result.id or "", updated_at=timezone.now())
        return self.get_screen_run(screen_run.id)

    def get_screen_run(self, screen_run_id: int) -> ScreenRun:
        return (
            ScreenRun.objects.select_related("workspace", "created_by", "universe", "job", "universe__workspace", "universe__source_upload")
            .prefetch_related("universe__entries")
            .get(pk=screen_run_id)
        )

    def execute_screen_run(
        self,
        *,
        screen_run_id: int,
        task: TrackedJobTask | None = None,
        job: JobRun | None = None,
    ) -> dict[str, object]:
        screen_run = self.get_screen_run(screen_run_id)
        active_job = job or screen_run.job
        tickers = [entry.normalized_ticker for entry in screen_run.universe.entries.all()]
        if not tickers:
            raise RuntimeError("The selected universe has no tickers to screen.")

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=5,
                current_step=f"Preparing {len(tickers)} tickers from the saved universe",
                metadata={"screen_run_id": screen_run.id},
            )
            active_job.refresh_from_db()

        provider_config = ProviderConfig(
            use_cache=screen_run.use_cache,
            refresh_cache=screen_run.refresh_cache,
            cache_ttl_hours=screen_run.cache_ttl_hours,
        )
        request_metadata = active_job.metadata.get("request", {}) if isinstance(active_job.metadata, dict) else {}
        if not isinstance(request_metadata, dict):
            request_metadata = {}
        provider_config = provider_config_from_request_payload(
            request_metadata.get("provider") if isinstance(request_metadata.get("provider"), dict) else None,
            use_cache=screen_run.use_cache,
            refresh_cache=screen_run.refresh_cache,
            cache_ttl_hours=screen_run.cache_ttl_hours,
        )
        config = ScreenConfig(
            top_n=screen_run.top_n,
            momentum_mode=screen_run.momentum_mode,
            sector_allowlist=set(screen_run.sector_allowlist) or None,
            min_market_cap=screen_run.min_market_cap,
            exclude_financials=screen_run.exclude_financials,
            exclude_utilities=screen_run.exclude_utilities,
            exclude_adrs=screen_run.exclude_adrs,
        )
        request = CoreScreenRequest(
            universe=UniverseRequest(tickers=tickers),
            config=config,
            provider=provider_config,
        )

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=20,
                current_step="Fetching fundamentals and ranking securities",
            )
            active_job.refresh_from_db()

        provider_name = provider_config.provider_name
        try:
            provider = self.provider_factory(provider_config)
        except Exception as exc:
            raise ProviderBuildError(
                f"Failed to initialize market data provider '{provider_name}': {exc}",
                provider_name=provider_name,
                workflow="screen",
            ) from exc

        try:
            response = self.core_screen_service_class(provider_factory=self.provider_factory).run(request, provider=provider)
        except Exception as exc:
            wrapped = wrap_provider_runtime_error(exc, provider_name=provider_name, workflow="screen")
            if wrapped is not None:
                raise wrapped from exc
            raise
        provider_info = provider_result_payload(provider, provider_config)

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=75,
                current_step="Persisting ranked rows and exclusions",
            )
            active_job.refresh_from_db()

        csv_bytes = response.ranked_frame.to_csv(index=False).encode("utf-8")
        export_filename = f"screen-run-{screen_run.id}-results.csv"
        stored_export = self.artifact_storage.store_artifact(
            workspace=screen_run.workspace,
            category="screens",
            original_filename=export_filename,
            content=csv_bytes,
        )

        result_rows = self._build_result_rows(screen_run, response.ranked_rows)
        exclusions = self._build_exclusions(screen_run, response.excluded_rows)
        summary = self._build_summary(screen_run, response, export_filename, provider_info)

        with transaction.atomic():
            ScreenResultRow.objects.filter(screen_run=screen_run).delete()
            ScreenExclusion.objects.filter(screen_run=screen_run).delete()
            ScreenResultRow.objects.bulk_create(result_rows)
            ScreenExclusion.objects.bulk_create(exclusions)

            screen_run.result_count = len(result_rows)
            screen_run.exclusion_count = len(exclusions)
            screen_run.resolved_ticker_count = response.resolved_universe.resolved_count
            screen_run.total_candidate_count = response.resolved_universe.total_candidates
            screen_run.summary = summary
            screen_run.export_storage_backend = stored_export.storage_backend
            screen_run.export_storage_key = stored_export.storage_key
            screen_run.export_filename = export_filename
            screen_run.export_checksum_sha256 = stored_export.checksum_sha256
            screen_run.export_size_bytes = stored_export.size_bytes
            screen_run.save(
                update_fields=[
                    "result_count",
                    "exclusion_count",
                    "resolved_ticker_count",
                    "total_candidate_count",
                    "summary",
                    "export_storage_backend",
                    "export_storage_key",
                    "export_filename",
                    "export_checksum_sha256",
                    "export_size_bytes",
                    "updated_at",
                ]
            )

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=95,
                current_step="Finalizing screen run",
            )

        return {
            "screen_run_id": screen_run.id,
            "result_count": len(result_rows),
            "exclusion_count": len(exclusions),
            "export_filename": export_filename,
            "top_tickers": [row.ticker for row in result_rows[:10]],
            "provider": provider_info,
        }

    def export_path(self, screen_run: ScreenRun):
        if not screen_run.has_export:
            raise FileNotFoundError("Screen export is not available.")
        return self.artifact_storage.resolve_path(screen_run.export_storage_key)

    @staticmethod
    def _build_result_rows(screen_run: ScreenRun, ranked_rows: list[dict[str, object | None]]) -> list[ScreenResultRow]:
        models: list[ScreenResultRow] = []
        for index, row in enumerate(ranked_rows, start=1):
            models.append(
                ScreenResultRow(
                    screen_run=screen_run,
                    position=index,
                    ticker=str(row.get("ticker") or ""),
                    company_name=str(row.get("company_name") or ""),
                    sector=str(row.get("sector") or ""),
                    industry=str(row.get("industry") or ""),
                    market_cap=_as_float(row.get("market_cap")),
                    ebit=_as_float(row.get("ebit")),
                    net_working_capital=_as_float(row.get("net_working_capital")),
                    enterprise_value=_as_float(row.get("enterprise_value")),
                    return_on_capital=_as_float(row.get("return_on_capital")),
                    earnings_yield=_as_float(row.get("earnings_yield")),
                    momentum_6m=_as_float(row.get("momentum_6m")),
                    roc_rank=_as_int(row.get("roc_rank")),
                    ey_rank=_as_int(row.get("ey_rank")),
                    momentum_rank=_as_int(row.get("momentum_rank")),
                    composite_score=_as_int(row.get("composite_score")),
                    final_score=_as_int(row.get("final_score")),
                    row_payload=row,
                )
            )
        return models

    @staticmethod
    def _build_exclusions(screen_run: ScreenRun, excluded_rows: list[dict[str, object | None]]) -> list[ScreenExclusion]:
        return [
            ScreenExclusion(
                screen_run=screen_run,
                ticker=str(row.get("ticker") or ""),
                reason=str(row.get("reason") or ""),
            )
            for row in excluded_rows
        ]

    @staticmethod
    def _build_summary(
        screen_run: ScreenRun,
        response,
        export_filename: str,
        provider_info: dict[str, object | None],
    ) -> dict[str, object]:
        return {
            "universe_name": screen_run.universe.name,
            "top_n": screen_run.top_n,
            "momentum_mode": screen_run.momentum_mode,
            "sector_allowlist": screen_run.sector_allowlist,
            "min_market_cap": screen_run.min_market_cap,
            "result_count": len(response.ranked_rows),
            "exclusion_count": len(response.excluded_rows),
            "resolved_universe": {
                "source_type": response.resolved_universe.source_type,
                "source_value": response.resolved_universe.source_value,
                "resolved_count": response.resolved_universe.resolved_count,
                "total_candidates": response.resolved_universe.total_candidates,
                "candidate_limit": response.resolved_universe.candidate_limit,
            },
            "top_tickers": [row.get("ticker") for row in response.ranked_rows[:10]],
            "export_filename": export_filename,
            "provider": provider_info,
        }


def _as_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
