from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from django.utils import timezone

from apps.core.context import current_correlation_id, current_request_id
from apps.jobs.limits import enforce_workspace_job_limits
from apps.jobs.models import JobRun
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
        return JobRun.objects.create(
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
            return job

        JobRun.objects.filter(pk=job.pk).update(celery_task_id=async_result.id or "", updated_at=timezone.now())
        return JobRun.objects.select_related("workspace", "created_by").get(pk=job.pk)
