from __future__ import annotations

import time
from statistics import mean

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.jobs.models import JobRun
from apps.strategy_templates.models import StrategyTemplate
from apps.strategy_templates.services import StrategyTemplateService


User = get_user_model()


class Command(BaseCommand):
    help = "Launch repeated runs from a saved strategy template and optionally wait for completion."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--template-id", type=int, required=True)
        parser.add_argument("--launch-count", type=int, default=3)
        parser.add_argument("--user-id", type=int)
        parser.add_argument("--wait", action="store_true")
        parser.add_argument("--poll-interval", type=float, default=5.0)
        parser.add_argument("--timeout-seconds", type=float, default=1800.0)

    def handle(self, *args, **options) -> None:
        template = (
            StrategyTemplate.objects.select_related("workspace", "created_by", "universe")
            .filter(pk=options["template_id"])
            .first()
        )
        if template is None:
            raise CommandError(f"Template {options['template_id']} does not exist.")

        if options["launch_count"] <= 0:
            raise CommandError("--launch-count must be positive.")

        launched_by = template.created_by
        if options.get("user_id") is not None:
            launched_by = User.objects.filter(pk=options["user_id"]).first()
            if launched_by is None:
                raise CommandError(f"User {options['user_id']} does not exist.")

        service = StrategyTemplateService()
        launched_job_ids: list[int] = []
        for index in range(options["launch_count"]):
            run = service.launch_template(template, launched_by=launched_by, trigger_source="load_test")
            launched_job_ids.append(run.job_id)
            self.stdout.write(
                f"Launched {template.workflow_kind} load-test run {index + 1}/{options['launch_count']} "
                f"job_id={run.job_id} run_id={run.id}"
            )

        if not options["wait"]:
            return

        pending_job_ids = set(launched_job_ids)
        deadline = time.monotonic() + options["timeout_seconds"]
        while pending_job_ids and time.monotonic() < deadline:
            completed_jobs = JobRun.objects.filter(pk__in=pending_job_ids).exclude(finished_at__isnull=True)
            for job in completed_jobs:
                pending_job_ids.discard(job.id)
            if pending_job_ids:
                time.sleep(max(0.5, options["poll_interval"]))

        if pending_job_ids:
            pending_list = ", ".join(str(job_id) for job_id in sorted(pending_job_ids))
            raise CommandError(f"Timed out waiting for jobs to finish: {pending_list}")

        terminal_jobs = list(JobRun.objects.filter(pk__in=launched_job_ids).order_by("id"))
        queue_latencies = [job.queue_latency_seconds for job in terminal_jobs if job.queue_latency_seconds is not None]
        run_durations = [job.run_duration_seconds for job in terminal_jobs if job.run_duration_seconds is not None]
        succeeded = sum(1 for job in terminal_jobs if job.state == JobRun.State.SUCCEEDED)
        failed = sum(1 for job in terminal_jobs if job.state == JobRun.State.FAILED)
        partial_failed = sum(1 for job in terminal_jobs if job.state == JobRun.State.PARTIAL_FAILED)

        self.stdout.write(
            self.style.SUCCESS(
                "Load test completed: "
                f"total={len(terminal_jobs)} succeeded={succeeded} failed={failed} partial_failed={partial_failed}"
            )
        )
        if queue_latencies:
            self.stdout.write(
                "Queue latency seconds: "
                f"avg={mean(queue_latencies):.2f} max={max(queue_latencies):.2f}"
            )
        if run_durations:
            self.stdout.write(
                "Run duration seconds: "
                f"avg={mean(run_durations):.2f} max={max(run_durations):.2f}"
            )
