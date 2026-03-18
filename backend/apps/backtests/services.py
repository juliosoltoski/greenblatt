from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.backtests.models import (
    BacktestEquityPoint,
    BacktestFinalHolding,
    BacktestReviewTarget,
    BacktestRun,
    BacktestTrade,
)
from apps.jobs.models import JobRun
from apps.jobs.services import JobService
from apps.universes.models import Universe
from apps.universes.services import ArtifactStorage
from apps.workspaces.models import Workspace
from greenblatt.models import BacktestConfig
from greenblatt.services import (
    BacktestRequest as CoreBacktestRequest,
    BacktestService as CoreBacktestService,
    ProviderConfig,
    UniverseRequest,
    build_yahoo_provider,
)


if TYPE_CHECKING:
    from apps.jobs.tasks import TrackedJobTask


@dataclass(frozen=True, slots=True)
class BacktestLaunchRequest:
    workspace: Workspace
    created_by: object
    universe: Universe
    start_date: date
    end_date: date
    initial_capital: float
    portfolio_size: int
    review_frequency: str
    benchmark: str
    momentum_mode: str
    sector_allowlist: list[str]
    min_market_cap: float | None
    use_cache: bool
    refresh_cache: bool
    cache_ttl_hours: float


class BacktestRunService:
    def __init__(
        self,
        *,
        job_service: JobService | None = None,
        artifact_storage: ArtifactStorage | None = None,
        provider_factory=None,
        core_backtest_service_class=None,
    ) -> None:
        self.job_service = job_service or JobService()
        self.artifact_storage = artifact_storage or ArtifactStorage()
        self.provider_factory = provider_factory or build_yahoo_provider
        self.core_backtest_service_class = core_backtest_service_class or CoreBacktestService

    def launch_backtest(self, request: BacktestLaunchRequest) -> BacktestRun:
        with transaction.atomic():
            job = self.job_service.create_job(
                workspace=request.workspace,
                created_by=request.created_by,
                job_type="backtest_run",
                metadata={
                    "request": {
                        "universe_id": request.universe.id,
                        "start_date": request.start_date.isoformat(),
                        "end_date": request.end_date.isoformat(),
                        "initial_capital": request.initial_capital,
                        "portfolio_size": request.portfolio_size,
                        "review_frequency": request.review_frequency,
                        "benchmark": request.benchmark,
                        "momentum_mode": request.momentum_mode,
                        "sector_allowlist": request.sector_allowlist,
                        "min_market_cap": request.min_market_cap,
                        "use_cache": request.use_cache,
                        "refresh_cache": request.refresh_cache,
                        "cache_ttl_hours": request.cache_ttl_hours,
                    }
                },
                current_step="Queued for backtesting",
            )
            backtest_run = BacktestRun.objects.create(
                workspace=request.workspace,
                created_by=request.created_by,
                universe=request.universe,
                job=job,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
                portfolio_size=request.portfolio_size,
                review_frequency=request.review_frequency,
                benchmark=request.benchmark,
                momentum_mode=request.momentum_mode,
                sector_allowlist=request.sector_allowlist,
                min_market_cap=request.min_market_cap,
                use_cache=request.use_cache,
                refresh_cache=request.refresh_cache,
                cache_ttl_hours=request.cache_ttl_hours,
            )
            job.metadata = {
                **job.metadata,
                "backtest_run_id": backtest_run.id,
            }
            job.updated_at = timezone.now()
            job.save(update_fields=["metadata", "updated_at"])

        return self.enqueue_backtest(backtest_run)

    def enqueue_backtest(self, backtest_run: BacktestRun) -> BacktestRun:
        from apps.backtests.tasks import run_backtest_job

        try:
            async_result = run_backtest_job.apply_async(
                kwargs={
                    "job_run_id": backtest_run.job_id,
                    "backtest_run_id": backtest_run.id,
                },
                queue="default",
            )
        except Exception as exc:
            job = backtest_run.job
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
            return self.get_backtest_run(backtest_run.id)

        JobRun.objects.filter(pk=backtest_run.job_id).update(celery_task_id=async_result.id or "", updated_at=timezone.now())
        return self.get_backtest_run(backtest_run.id)

    def get_backtest_run(self, backtest_run_id: int) -> BacktestRun:
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
            .get(pk=backtest_run_id)
        )

    def execute_backtest_run(
        self,
        *,
        backtest_run_id: int,
        task: TrackedJobTask | None = None,
        job: JobRun | None = None,
    ) -> dict[str, object]:
        backtest_run = self.get_backtest_run(backtest_run_id)
        active_job = job or backtest_run.job
        tickers = [entry.normalized_ticker for entry in backtest_run.universe.entries.all()]
        if not tickers:
            raise RuntimeError("The selected universe has no tickers to backtest.")

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=5,
                current_step=f"Preparing {len(tickers)} tickers from the saved universe",
                metadata={"backtest_run_id": backtest_run.id},
            )
            active_job.refresh_from_db()

        provider_config = ProviderConfig(
            use_cache=backtest_run.use_cache,
            refresh_cache=backtest_run.refresh_cache,
            cache_ttl_hours=backtest_run.cache_ttl_hours,
        )
        config = BacktestConfig(
            start_date=backtest_run.start_date,
            end_date=backtest_run.end_date,
            initial_capital=backtest_run.initial_capital,
            portfolio_size=backtest_run.portfolio_size,
            review_frequency=backtest_run.review_frequency,
            benchmark=backtest_run.benchmark,
            momentum_mode=backtest_run.momentum_mode,
            sector_allowlist=set(backtest_run.sector_allowlist) or None,
            min_market_cap=backtest_run.min_market_cap,
        )
        request = CoreBacktestRequest(
            universe=UniverseRequest(tickers=tickers),
            config=config,
            provider=provider_config,
        )

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=20,
                current_step="Running backtest simulation and building equity curve",
            )
            active_job.refresh_from_db()

        provider = self.provider_factory(provider_config)
        response = self.core_backtest_service_class(provider_factory=self.provider_factory).run(request, provider=provider)

        if task is not None:
            task.update_progress(
                active_job,
                progress_percent=80,
                current_step="Persisting equity points, trades, review targets, and holdings",
            )
            active_job.refresh_from_db()

        export_filename = f"backtest-run-{backtest_run.id}-artifacts.zip"
        export_bytes = self._build_export_archive(response)
        stored_export = self.artifact_storage.store_artifact(
            workspace=backtest_run.workspace,
            category="backtests",
            original_filename=export_filename,
            content=export_bytes,
        )

        equity_points = self._build_equity_points(backtest_run, response.equity_curve_rows)
        trades = self._build_trades(backtest_run, response.trade_rows)
        review_targets = self._build_review_targets(backtest_run, response.review_target_rows)
        final_holdings = self._build_final_holdings(backtest_run, response.final_holding_rows)
        summary = self._build_summary(backtest_run, response, export_filename)

        with transaction.atomic():
            BacktestEquityPoint.objects.filter(backtest_run=backtest_run).delete()
            BacktestTrade.objects.filter(backtest_run=backtest_run).delete()
            BacktestReviewTarget.objects.filter(backtest_run=backtest_run).delete()
            BacktestFinalHolding.objects.filter(backtest_run=backtest_run).delete()

            BacktestEquityPoint.objects.bulk_create(equity_points)
            BacktestTrade.objects.bulk_create(trades)
            BacktestReviewTarget.objects.bulk_create(review_targets)
            BacktestFinalHolding.objects.bulk_create(final_holdings)

            backtest_run.equity_point_count = len(equity_points)
            backtest_run.trade_count = len(trades)
            backtest_run.review_target_count = len(review_targets)
            backtest_run.final_holding_count = len(final_holdings)
            backtest_run.summary = summary
            backtest_run.export_storage_backend = stored_export.storage_backend
            backtest_run.export_storage_key = stored_export.storage_key
            backtest_run.export_filename = export_filename
            backtest_run.export_checksum_sha256 = stored_export.checksum_sha256
            backtest_run.export_size_bytes = stored_export.size_bytes
            backtest_run.save(
                update_fields=[
                    "equity_point_count",
                    "trade_count",
                    "review_target_count",
                    "final_holding_count",
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
                current_step="Finalizing backtest run",
            )

        return {
            "backtest_run_id": backtest_run.id,
            "equity_point_count": len(equity_points),
            "trade_count": len(trades),
            "review_target_count": len(review_targets),
            "final_holding_count": len(final_holdings),
            "export_filename": export_filename,
        }

    def export_path(self, backtest_run: BacktestRun):
        if not backtest_run.has_export:
            raise FileNotFoundError("Backtest export is not available.")
        return self.artifact_storage.resolve_path(backtest_run.export_storage_key)

    @staticmethod
    def _build_equity_points(
        backtest_run: BacktestRun,
        rows: list[dict[str, object | None]],
    ) -> list[BacktestEquityPoint]:
        return [
            BacktestEquityPoint(
                backtest_run=backtest_run,
                position=index,
                date=date.fromisoformat(str(row["date"])),
                cash=float(row.get("cash") or 0),
                equity=float(row.get("equity") or 0),
                positions=int(row.get("positions") or 0),
                benchmark_equity=_as_float(row.get("benchmark_equity")),
            )
            for index, row in enumerate(rows, start=1)
        ]

    @staticmethod
    def _build_trades(
        backtest_run: BacktestRun,
        rows: list[dict[str, object | None]],
    ) -> list[BacktestTrade]:
        return [
            BacktestTrade(
                backtest_run=backtest_run,
                position=index,
                date=date.fromisoformat(str(row["date"])),
                ticker=str(row.get("ticker") or ""),
                side=str(row.get("side") or ""),
                shares=float(row.get("shares") or 0),
                price=float(row.get("price") or 0),
                proceeds=float(row.get("proceeds") or 0),
                reason=str(row.get("reason") or ""),
            )
            for index, row in enumerate(rows, start=1)
        ]

    @staticmethod
    def _build_review_targets(
        backtest_run: BacktestRun,
        rows: list[dict[str, object | None]],
    ) -> list[BacktestReviewTarget]:
        return [
            BacktestReviewTarget(
                backtest_run=backtest_run,
                position=index,
                date=date.fromisoformat(str(row["date"])),
                target_rank=int(row.get("target_rank") or 0),
                ticker=str(row.get("ticker") or ""),
                company_name=str(row.get("company_name") or ""),
                sector=str(row.get("sector") or ""),
                industry=str(row.get("industry") or ""),
                final_score=_as_int(row.get("final_score")),
                composite_score=_as_int(row.get("composite_score")),
                roc_rank=_as_int(row.get("roc_rank")),
                ey_rank=_as_int(row.get("ey_rank")),
                momentum_rank=_as_int(row.get("momentum_rank")),
            )
            for index, row in enumerate(rows, start=1)
        ]

    @staticmethod
    def _build_final_holdings(
        backtest_run: BacktestRun,
        rows: list[dict[str, object | None]],
    ) -> list[BacktestFinalHolding]:
        return [
            BacktestFinalHolding(
                backtest_run=backtest_run,
                position=index,
                ticker=str(row.get("ticker") or ""),
                shares=float(row.get("shares") or 0),
                entry_date=date.fromisoformat(str(row["entry_date"])),
                entry_price=float(row.get("entry_price") or 0),
                score=_as_int(row.get("score")),
            )
            for index, row in enumerate(rows, start=1)
        ]

    @staticmethod
    def _build_summary(backtest_run: BacktestRun, response, export_filename: str) -> dict[str, object]:
        summary = {
            **response.summary_payload,
            "universe_name": backtest_run.universe.name,
            "benchmark": backtest_run.benchmark or None,
            "review_frequency": backtest_run.review_frequency,
            "momentum_mode": backtest_run.momentum_mode,
            "sector_allowlist": backtest_run.sector_allowlist,
            "min_market_cap": backtest_run.min_market_cap,
            "equity_point_count": len(response.equity_curve_rows),
            "trade_count": len(response.trade_rows),
            "review_target_count": len(response.review_target_rows),
            "final_holding_count": len(response.final_holding_rows),
            "trade_summary": response.trade_summary_rows,
            "export_filename": export_filename,
        }
        return summary

    @staticmethod
    def _build_export_archive(response) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("summary.json", json.dumps(response.summary_payload, indent=2, sort_keys=True))
            archive.writestr("equity_curve.csv", response.equity_curve_frame.to_csv(index=False))
            archive.writestr("trades.csv", response.trades_frame.to_csv(index=False))
            archive.writestr("final_holdings.csv", response.final_holdings_frame.to_csv(index=False))
            if response.review_targets_frame is not None:
                archive.writestr("review_targets.csv", response.review_targets_frame.to_csv(index=False))
            if response.trade_summary_frame is not None:
                archive.writestr("trade_summary.csv", response.trade_summary_frame.to_csv(index=False))
        return buffer.getvalue()


def _as_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    return int(value)

