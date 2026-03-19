from __future__ import annotations

from celery import shared_task

from apps.automation.services import NotificationService, ScheduleService


@shared_task(name="automation.run_scheduled_template")
def run_scheduled_template(*, schedule_id: int) -> dict[str, object]:
    run = ScheduleService().launch_schedule(ScheduleService().get_schedule(schedule_id), trigger_source="scheduler")
    return {
        "schedule_id": schedule_id,
        "workflow_kind": run.source_template.workflow_kind if getattr(run, "source_template", None) else "",
        "run_id": run.id,
        "job_id": run.job_id,
        "job_state": run.job.state,
    }


@shared_task(name="automation.send_notification_digests")
def send_notification_digests() -> dict[str, int]:
    return {"sent_count": NotificationService().dispatch_pending_digests()}
