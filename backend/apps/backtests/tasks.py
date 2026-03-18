from __future__ import annotations

from celery import shared_task

from apps.automation.services import NotificationService
from apps.backtests.services import BacktestRunService
from apps.jobs.tasks import TrackedJobTask, _run_with_tracking


@shared_task(bind=True, base=TrackedJobTask, name="backtests.run_backtest_job")
def run_backtest_job(
    self: TrackedJobTask,
    job_run_id: int,
    *,
    backtest_run_id: int,
) -> dict[str, object]:
    service = BacktestRunService()
    try:
        result = _run_with_tracking(
            self,
            job_run_id,
            lambda job: service.execute_backtest_run(backtest_run_id=backtest_run_id, task=self, job=job),
        )
    except Exception:
        backtest_run = service.get_backtest_run(backtest_run_id)
        if backtest_run.job.is_terminal:
            NotificationService().dispatch_for_backtest_run(backtest_run)
        raise

    NotificationService().dispatch_for_backtest_run(service.get_backtest_run(backtest_run_id))
    return result
