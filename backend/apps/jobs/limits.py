from __future__ import annotations

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import Throttled

from apps.core.metrics import record_workspace_concurrency_rejection
from apps.jobs.models import JobRun
from apps.workspaces.models import Workspace


ACTIVE_STATES = [JobRun.State.QUEUED, JobRun.State.RUNNING]
RESEARCH_JOB_TYPES = {"screen_run", "backtest_run"}


class WorkspaceConcurrencyLimitExceeded(Throttled):
    default_code = "workspace_concurrency_limit"

    def __init__(self, *, detail: str):
        super().__init__(wait=None, detail=detail)


def enforce_workspace_job_limits(*, workspace: Workspace, job_type: str) -> None:
    with transaction.atomic():
        locked_workspace = Workspace.objects.select_for_update().get(pk=workspace.pk)
        active_jobs = JobRun.objects.filter(workspace=locked_workspace, state__in=ACTIVE_STATES)

        total_limit = int(getattr(settings, "WORKSPACE_MAX_CONCURRENT_JOBS", 0) or 0)
        if total_limit > 0 and active_jobs.count() >= total_limit:
            record_workspace_concurrency_rejection(job_type=job_type, limit_name="total_jobs")
            raise WorkspaceConcurrencyLimitExceeded(
                detail=f"Workspace concurrency limit reached ({total_limit} active jobs)."
            )

        research_limit = int(getattr(settings, "WORKSPACE_MAX_CONCURRENT_RESEARCH_JOBS", 0) or 0)
        if job_type in RESEARCH_JOB_TYPES and research_limit > 0:
            active_research = active_jobs.filter(job_type__in=RESEARCH_JOB_TYPES).count()
            if active_research >= research_limit:
                record_workspace_concurrency_rejection(job_type=job_type, limit_name="research_jobs")
                raise WorkspaceConcurrencyLimitExceeded(
                    detail=f"Workspace research concurrency limit reached ({research_limit} active screen/backtest jobs)."
                )

        smoke_limit = int(getattr(settings, "WORKSPACE_MAX_CONCURRENT_SMOKE_JOBS", 0) or 0)
        if job_type == "smoke_test" and smoke_limit > 0:
            active_smoke = active_jobs.filter(job_type="smoke_test").count()
            if active_smoke >= smoke_limit:
                record_workspace_concurrency_rejection(job_type=job_type, limit_name="smoke_jobs")
                raise WorkspaceConcurrencyLimitExceeded(
                    detail=f"Workspace smoke-test concurrency limit reached ({smoke_limit} active smoke jobs)."
                )
