from __future__ import annotations

from apps.jobs.models import JobRun
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
        "metadata": job.metadata,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "is_terminal": job.is_terminal,
    }
