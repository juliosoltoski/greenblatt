from __future__ import annotations

from apps.jobs.models import JobEvent, JobRun
from apps.workspaces.presenters import serialize_workspace


def serialize_job(job: JobRun) -> dict[str, object | None]:
    return {
        "id": job.id,
        "workspace": serialize_workspace(job.workspace),
        "created_by_id": job.created_by_id,
        "job_type": job.job_type,
        "state": job.state,
        "progress_percent": job.progress_percent,
        "current_step": job.current_step,
        "error_code": job.error_code or None,
        "error_message": job.error_message or None,
        "retry_count": job.retry_count,
        "celery_task_id": job.celery_task_id or None,
        "cancel_requested_by_id": job.cancel_requested_by_id,
        "cancel_requested_at": job.cancel_requested_at.isoformat() if job.cancel_requested_at else None,
        "cancellation_requested": job.cancellation_requested,
        "metadata": job.metadata,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "queue_latency_seconds": job.queue_latency_seconds,
        "run_duration_seconds": job.run_duration_seconds,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "is_terminal": job.is_terminal,
    }


def serialize_job_event(event: JobEvent) -> dict[str, object | None]:
    return {
        "id": event.id,
        "workspace": serialize_workspace(event.workspace),
        "job_id": event.job_id,
        "level": event.level,
        "event_type": event.event_type,
        "message": event.message,
        "progress_percent": event.progress_percent,
        "metadata": event.metadata,
        "created_at": event.created_at.isoformat(),
    }
