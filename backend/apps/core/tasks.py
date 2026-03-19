from __future__ import annotations

from celery import shared_task

from apps.core.provider_operations import ProviderCacheWarmJobService
from apps.jobs.tasks import TrackedJobTask, _run_with_tracking


class ProviderCacheWarmTask(TrackedJobTask):
    abstract = True
    initial_step = "Starting provider cache warm"
    completion_step = "Provider cache warm completed"


@shared_task(bind=True, base=ProviderCacheWarmTask, name="core.run_provider_cache_warm_job")
def run_provider_cache_warm_job(self: ProviderCacheWarmTask, job_run_id: int) -> dict[str, object]:
    return _run_with_tracking(
        self,
        job_run_id,
        lambda job: ProviderCacheWarmJobService().execute_cache_warm_job(job_run_id=job_run_id, task=self, job=job),
    )
