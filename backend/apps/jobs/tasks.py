from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Callable

from celery import Task, shared_task
from django.utils import timezone

from apps.core.context import clear_observability_context, set_observability_context
from apps.jobs.errors import provider_failure_metadata
from apps.jobs.models import JobEvent, JobRun
from apps.jobs.retries import RetryableJobError, error_code_for_exception, is_retryable_exception, merge_metadata, next_retry_delay_seconds


logger = logging.getLogger(__name__)


class JobCancelledError(RuntimeError):
    pass


class TrackedJobTask(Task):
    abstract = True
    max_retries = 2
    initial_step = "Starting job"
    completion_step = "Completed"

    def update_progress(
        self,
        job: JobRun,
        *,
        progress_percent: int | None = None,
        current_step: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JobRun:
        self.check_for_cancellation(job)
        if progress_percent is not None:
            job.progress_percent = max(0, min(100, int(progress_percent)))
        if current_step is not None:
            job.current_step = current_step
        if metadata:
            job.metadata = merge_metadata(job.metadata, metadata)
        self._save_job(job, "progress_percent", "current_step", "metadata")
        self._record_event(
            job,
            event_type="progress",
            message=current_step or "Job progress updated.",
            progress_percent=job.progress_percent,
            metadata=metadata,
        )
        return job

    @staticmethod
    def _get_job(job_run_id: int) -> JobRun:
        return JobRun.objects.get(pk=job_run_id)

    def _mark_running(self, job: JobRun) -> None:
        set_observability_context(
            request_id=str(job.metadata.get("request_id") or ""),
            correlation_id=str(job.metadata.get("correlation_id") or ""),
            job_id=job.id,
            task_id=self.request.id,
            workspace_id=job.workspace_id,
            user_id=job.created_by_id,
        )
        if not job.started_at:
            job.started_at = timezone.now()
        if not job.celery_task_id:
            job.celery_task_id = self.request.id or ""
        job.state = JobRun.State.RUNNING
        job.current_step = self.initial_step
        job.error_code = ""
        job.error_message = ""
        job.finished_at = None
        self._save_job(job, "started_at", "celery_task_id", "state", "current_step", "error_code", "error_message", "finished_at")
        self._record_event(job, event_type="running", message=self.initial_step, progress_percent=job.progress_percent)

    def _mark_retry(self, job: JobRun, exc: Exception, countdown: int) -> None:
        job.state = JobRun.State.QUEUED
        job.retry_count = self.request.retries + 1
        job.current_step = f"Retry scheduled in {countdown}s"
        job.error_code = error_code_for_exception(exc)
        job.error_message = str(exc)
        job.finished_at = None
        job.metadata = merge_metadata(
            job.metadata,
            {
                "last_error": {
                    "code": job.error_code,
                    "message": job.error_message,
                    "retryable": True,
                }
            },
        )
        self._save_job(job, "state", "retry_count", "current_step", "error_code", "error_message", "finished_at", "metadata")
        self._record_event(
            job,
            event_type="retry_scheduled",
            level=JobEvent.Level.WARNING,
            message=job.current_step,
            progress_percent=job.progress_percent,
            metadata={"error_code": job.error_code, "countdown_seconds": countdown},
        )

    def _mark_failed(self, job: JobRun, exc: Exception) -> None:
        job.state = JobRun.State.FAILED
        job.error_code = error_code_for_exception(exc)
        job.error_message = str(exc)
        job.finished_at = timezone.now()
        provider_failure = provider_failure_metadata(exc)
        metadata_updates = {
            "last_error": {
                "code": job.error_code,
                "message": job.error_message,
                "retryable": False,
                "exception_type": exc.__class__.__name__,
                "traceback": traceback.format_exc(),
            }
        }
        if provider_failure is not None:
            metadata_updates["provider_failure"] = provider_failure
        job.metadata = merge_metadata(
            job.metadata,
            metadata_updates,
        )
        self._save_job(job, "state", "error_code", "error_message", "finished_at", "metadata")
        self._record_event(
            job,
            event_type="failed",
            level=JobEvent.Level.ERROR,
            message=job.error_message or "Job failed.",
            progress_percent=job.progress_percent,
            metadata=metadata_updates,
        )
        if provider_failure is not None:
            self._record_event(
                job,
                event_type="provider_failure",
                level=JobEvent.Level.ERROR,
                message=f"Provider failure: {provider_failure.get('provider_name', 'unknown')}",
                progress_percent=job.progress_percent,
                metadata=provider_failure,
            )

    def _mark_succeeded(self, job: JobRun, result: Any) -> None:
        job.state = JobRun.State.SUCCEEDED
        job.progress_percent = 100
        job.current_step = self.completion_step
        job.error_code = ""
        job.error_message = ""
        job.finished_at = timezone.now()
        job.metadata = merge_metadata(job.metadata, {"result": result})
        self._save_job(
            job,
            "state",
            "progress_percent",
            "current_step",
            "error_code",
            "error_message",
            "finished_at",
            "metadata",
        )
        self._record_event(
            job,
            event_type="succeeded",
            message=self.completion_step,
            progress_percent=job.progress_percent,
            metadata={"result": result if isinstance(result, dict) else {"type": type(result).__name__}},
        )

    def _mark_cancelled(self, job: JobRun, exc: Exception | None = None) -> None:
        job.state = JobRun.State.CANCELLED
        job.current_step = "Cancelled"
        job.error_code = "cancelled"
        job.error_message = str(exc or "Job cancelled.")
        job.finished_at = timezone.now()
        job.metadata = merge_metadata(
            job.metadata,
            {
                "last_error": {
                    "code": job.error_code,
                    "message": job.error_message,
                    "retryable": False,
                }
            },
        )
        self._save_job(job, "state", "current_step", "error_code", "error_message", "finished_at", "metadata")
        self._record_event(
            job,
            event_type="cancelled",
            level=JobEvent.Level.WARNING,
            message=job.error_message,
            progress_percent=job.progress_percent,
        )

    def check_for_cancellation(self, job: JobRun) -> None:
        job.refresh_from_db(fields=["state", "cancel_requested_at", "updated_at"])
        if job.cancel_requested_at is not None and not job.is_terminal:
            raise JobCancelledError("Job cancellation was requested.")

    @staticmethod
    def _record_event(
        job: JobRun,
        *,
        event_type: str,
        message: str,
        level: str = JobEvent.Level.INFO,
        progress_percent: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        JobEvent.objects.create(
            workspace=job.workspace,
            job=job,
            level=level,
            event_type=event_type,
            message=message[:255],
            progress_percent=progress_percent,
            metadata=metadata or {},
        )

    @staticmethod
    def _save_job(job: JobRun, *fields: str) -> None:
        unique_fields = list(dict.fromkeys([*fields, "updated_at"]))
        job.updated_at = timezone.now()
        job.save(update_fields=unique_fields)


def _run_with_tracking(task: TrackedJobTask, job_run_id: int, work: Callable[[JobRun], Any]) -> Any:
    job = task._get_job(job_run_id)
    task._mark_running(job)

    try:
        task.check_for_cancellation(job)
        result = work(job)
    except JobCancelledError as exc:
        task._mark_cancelled(job, exc)
        return {"message": "Job cancelled."}
    except Exception as exc:
        if is_retryable_exception(exc) and task.request.retries < task.max_retries:
            countdown = next_retry_delay_seconds(task.request.retries)
            task._mark_retry(job, exc, countdown)
            logger.warning("Retrying job %s after %s seconds because of %s", job.pk, countdown, exc)
            raise task.retry(exc=exc, countdown=countdown, max_retries=task.max_retries)

        task._mark_failed(job, exc)
        logger.exception("Job %s failed", job.pk)
        raise
    finally:
        clear_observability_context()

    task._mark_succeeded(job, result)
    return result


def _perform_smoke_job(
    task: TrackedJobTask,
    job: JobRun,
    *,
    step_count: int,
    step_delay_ms: int,
    failure_mode: str,
) -> dict[str, object]:
    if failure_mode == "retry_once" and task.request.retries == 0:
        raise RetryableJobError("Synthetic transient failure requested.", error_code="synthetic_retry")

    for index in range(step_count):
        task.check_for_cancellation(job)
        if step_delay_ms > 0:
            time.sleep(step_delay_ms / 1000)
        percent_complete = int(((index + 1) / step_count) * 95)
        task.update_progress(
            job,
            progress_percent=percent_complete,
            current_step=f"Processing step {index + 1}/{step_count}",
            metadata={
                "step_count": step_count,
                "steps_completed": index + 1,
                "step_delay_ms": step_delay_ms,
                "failure_mode": failure_mode,
            },
        )
        job.refresh_from_db()

    if failure_mode == "fail":
        raise RuntimeError("Synthetic smoke failure requested.")

    return {
        "message": "Smoke task completed successfully.",
        "step_count": step_count,
        "step_delay_ms": step_delay_ms,
        "failure_mode": failure_mode,
    }


@shared_task(bind=True, base=TrackedJobTask, name="jobs.run_smoke_job")
def run_smoke_job(
    self: TrackedJobTask,
    job_run_id: int,
    *,
    step_count: int = 4,
    step_delay_ms: int = 750,
    failure_mode: str = "success",
) -> dict[str, object]:
    return _run_with_tracking(
        self,
        job_run_id,
        lambda job: _perform_smoke_job(
            self,
            job,
            step_count=step_count,
            step_delay_ms=step_delay_ms,
            failure_mode=failure_mode,
        ),
    )
