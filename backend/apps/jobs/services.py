from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from django.utils import timezone

from apps.core.context import current_correlation_id, current_request_id
from apps.jobs.limits import enforce_workspace_job_limits
from apps.jobs.models import JobEvent, JobRun
from apps.jobs.tasks import run_smoke_job
from apps.workspaces.models import Workspace


@dataclass(frozen=True, slots=True)
class SmokeJobRequest:
    workspace: Workspace
    created_by: object
    step_count: int
    step_delay_ms: int
    failure_mode: str


class JobDispatchError(RuntimeError):
    pass


class JobService:
    @staticmethod
    def record_event(
        job: JobRun,
        *,
        event_type: str,
        message: str,
        level: str = JobEvent.Level.INFO,
        progress_percent: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> JobEvent:
        return JobEvent.objects.create(
            workspace=job.workspace,
            job=job,
            level=level,
            event_type=event_type,
            message=message[:255],
            progress_percent=progress_percent,
            metadata=metadata or {},
        )

    def create_job(
        self,
        *,
        workspace: Workspace,
        created_by,
        job_type: str,
        metadata: dict[str, object] | None = None,
        current_step: str = "Queued",
    ) -> JobRun:
        enforce_workspace_job_limits(workspace=workspace, job_type=job_type)
        correlation_id = current_correlation_id() or uuid4().hex
        request_id = current_request_id()
        job = JobRun.objects.create(
            workspace=workspace,
            created_by=created_by,
            job_type=job_type,
            state=JobRun.State.QUEUED,
            progress_percent=0,
            current_step=current_step,
            metadata={
                **(metadata or {}),
                "request_id": request_id,
                "correlation_id": correlation_id,
            },
        )
        self.record_event(
            job,
            event_type="queued",
            message=current_step,
            progress_percent=0,
            metadata={"job_type": job.job_type},
        )
        return job

    def launch_smoke_job(self, request: SmokeJobRequest) -> JobRun:
        job = self.create_job(
            workspace=request.workspace,
            created_by=request.created_by,
            job_type="smoke_test",
            metadata={
                "request": {
                    "step_count": request.step_count,
                    "step_delay_ms": request.step_delay_ms,
                    "failure_mode": request.failure_mode,
                }
            },
        )
        return self.enqueue_smoke_job(job, request=request)

    def enqueue_smoke_job(self, job: JobRun, *, request: SmokeJobRequest) -> JobRun:
        try:
            async_result = run_smoke_job.apply_async(
                kwargs={
                    "job_run_id": job.id,
                    "step_count": request.step_count,
                    "step_delay_ms": request.step_delay_ms,
                    "failure_mode": request.failure_mode,
                },
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
            self.record_event(
                job,
                event_type="dispatch_failed",
                level=JobEvent.Level.ERROR,
                message="Failed to dispatch smoke job.",
                metadata={"error": str(exc)},
            )
            return job

        JobRun.objects.filter(pk=job.pk).update(celery_task_id=async_result.id or "", updated_at=timezone.now())
        refreshed = JobRun.objects.select_related("workspace", "created_by").get(pk=job.pk)
        self.record_event(
            refreshed,
            event_type="dispatched",
            message="Smoke job dispatched to Celery.",
            metadata={"celery_task_id": async_result.id or ""},
        )
        return refreshed

    def request_cancellation(self, job: JobRun, *, requested_by) -> JobRun:
        if job.is_terminal:
            return job
        job.cancel_requested_by = requested_by
        job.cancel_requested_at = timezone.now()
        job.updated_at = timezone.now()
        job.save(update_fields=["cancel_requested_by", "cancel_requested_at", "updated_at"])
        self.record_event(
            job,
            event_type="cancel_requested",
            level=JobEvent.Level.WARNING,
            message="Cancellation requested.",
            metadata={"requested_by_id": getattr(requested_by, "id", None)},
        )
        return job

    def retry_job(self, job: JobRun, *, requested_by) -> JobRun:
        if job.job_type != "smoke_test":
            raise JobDispatchError("Retry is currently supported only for smoke-test jobs.")
        request_payload = job.metadata.get("request") if isinstance(job.metadata, dict) else None
        if not isinstance(request_payload, dict):
            raise JobDispatchError("This job does not have a retryable request payload.")
        request = SmokeJobRequest(
            workspace=job.workspace,
            created_by=requested_by,
            step_count=int(request_payload.get("step_count", 4)),
            step_delay_ms=int(request_payload.get("step_delay_ms", 750)),
            failure_mode=str(request_payload.get("failure_mode", "success")),
        )
        retried = self.launch_smoke_job(request)
        self.record_event(
            retried,
            event_type="retry_spawned",
            message=f"Retry created from job #{job.id}.",
            metadata={"retried_from_job_id": job.id},
        )
        return retried
