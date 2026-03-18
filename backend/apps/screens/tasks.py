from __future__ import annotations

from celery import shared_task

from apps.automation.services import NotificationService
from apps.jobs.tasks import TrackedJobTask, _run_with_tracking
from apps.screens.services import ScreenRunService


@shared_task(bind=True, base=TrackedJobTask, name="screens.run_screen_job")
def run_screen_job(
    self: TrackedJobTask,
    job_run_id: int,
    *,
    screen_run_id: int,
) -> dict[str, object]:
    service = ScreenRunService()
    try:
        result = _run_with_tracking(
            self,
            job_run_id,
            lambda job: service.execute_screen_run(screen_run_id=screen_run_id, task=self, job=job),
        )
    except Exception:
        screen_run = service.get_screen_run(screen_run_id)
        if screen_run.job.is_terminal:
            NotificationService().dispatch_for_screen_run(screen_run)
        raise

    NotificationService().dispatch_for_screen_run(service.get_screen_run(screen_run_id))
    return result
