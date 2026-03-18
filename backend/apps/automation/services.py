from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.template.defaultfilters import slugify
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from apps.automation.models import AlertRule, NotificationEvent, RunSchedule
from apps.backtests.models import BacktestRun
from apps.jobs.models import JobRun
from apps.screens.models import ScreenRun
from apps.strategy_templates.models import StrategyTemplate
from apps.strategy_templates.services import StrategyTemplateService
from apps.workspaces.models import Workspace


logger = logging.getLogger(__name__)

FAILURE_STATES = {
    JobRun.State.FAILED,
    JobRun.State.CANCELLED,
    JobRun.State.PARTIAL_FAILED,
}


@dataclass(frozen=True, slots=True)
class RunScheduleDefinition:
    workspace: Workspace
    created_by: object
    strategy_template: StrategyTemplate
    name: str
    description: str
    timezone: str
    cron_minute: str
    cron_hour: str
    cron_day_of_week: str
    cron_day_of_month: str
    cron_month_of_year: str
    is_enabled: bool
    notify_email: str
    notify_on_success: bool
    notify_on_failure: bool


@dataclass(frozen=True, slots=True)
class AlertRuleDefinition:
    workspace: Workspace
    created_by: object
    name: str
    description: str
    event_type: str
    workflow_kind: str
    destination_email: str
    ticker: str
    top_n_threshold: int | None
    is_enabled: bool
    strategy_template: StrategyTemplate | None = None


class ScheduleService:
    def create_schedule(self, definition: RunScheduleDefinition) -> RunSchedule:
        with transaction.atomic():
            schedule = RunSchedule.objects.create(
                workspace=definition.workspace,
                created_by=definition.created_by,
                strategy_template=definition.strategy_template,
                name=definition.name,
                description=definition.description,
                timezone=definition.timezone,
                cron_minute=definition.cron_minute,
                cron_hour=definition.cron_hour,
                cron_day_of_week=definition.cron_day_of_week,
                cron_day_of_month=definition.cron_day_of_month,
                cron_month_of_year=definition.cron_month_of_year,
                is_enabled=definition.is_enabled,
                notify_email=definition.notify_email,
                notify_on_success=definition.notify_on_success,
                notify_on_failure=definition.notify_on_failure,
            )
            self.sync_periodic_task(schedule)
        return self.get_schedule(schedule.id)

    def update_schedule(self, schedule: RunSchedule, **attrs) -> RunSchedule:
        for field, value in attrs.items():
            if value is not None:
                setattr(schedule, field, value)
        schedule.save()
        self.sync_periodic_task(schedule)
        return self.get_schedule(schedule.id)

    def delete_schedule(self, schedule: RunSchedule) -> None:
        periodic_task = schedule.periodic_task
        schedule.delete()
        if periodic_task is not None:
            periodic_task.delete()

    def get_schedule(self, schedule_id: int) -> RunSchedule:
        return (
            RunSchedule.objects.select_related(
                "workspace",
                "workspace__owner",
                "created_by",
                "strategy_template",
                "strategy_template__workspace",
                "strategy_template__created_by",
                "strategy_template__universe",
                "strategy_template__universe__workspace",
                "strategy_template__universe__source_upload",
                "periodic_task",
            )
            .prefetch_related("strategy_template__universe__entries")
            .get(pk=schedule_id)
        )

    def sync_periodic_task(self, schedule: RunSchedule) -> RunSchedule:
        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute=schedule.cron_minute,
            hour=schedule.cron_hour,
            day_of_week=schedule.cron_day_of_week,
            day_of_month=schedule.cron_day_of_month,
            month_of_year=schedule.cron_month_of_year,
            timezone=schedule.timezone,
        )
        task_name = f"greenblatt-schedule-{schedule.id}-{slugify(schedule.name)[:80]}"
        kwargs = json.dumps({"schedule_id": schedule.id}, sort_keys=True)
        periodic_task = schedule.periodic_task or PeriodicTask()
        periodic_task.name = task_name
        periodic_task.task = "automation.run_scheduled_template"
        periodic_task.crontab = crontab
        periodic_task.kwargs = kwargs
        periodic_task.enabled = schedule.is_enabled
        periodic_task.one_off = False
        periodic_task.description = (
            f"Recurring {schedule.strategy_template.workflow_kind} launch for template #{schedule.strategy_template_id}"
        )
        periodic_task.save()
        if schedule.periodic_task_id != periodic_task.id:
            schedule.periodic_task = periodic_task
            schedule.save(update_fields=["periodic_task", "updated_at"])
        return self.get_schedule(schedule.id)

    def launch_schedule(self, schedule: RunSchedule, *, trigger_source: str = "schedule") -> ScreenRun | BacktestRun:
        schedule = self.get_schedule(schedule.id)
        try:
            run = StrategyTemplateService().launch_template(
                schedule.strategy_template,
                launched_by=schedule.created_by,
                schedule_id=schedule.id,
                trigger_source=trigger_source,
            )
        except Exception as exc:
            schedule.last_triggered_at = timezone.now()
            schedule.last_launch_status = "dispatch_exception"
            schedule.last_error_message = str(exc)
            schedule.save(update_fields=["last_triggered_at", "last_launch_status", "last_error_message", "updated_at"])
            if schedule.notify_on_failure:
                NotificationService().dispatch_schedule_exception(schedule, exc)
            raise

        schedule.last_triggered_at = timezone.now()
        schedule.last_launch_status = run.job.state
        schedule.last_run_workflow_kind = schedule.strategy_template.workflow_kind
        schedule.last_run_id = run.id
        schedule.last_job_run_id = run.job_id
        schedule.last_error_message = run.job.error_message
        schedule.save(
            update_fields=[
                "last_triggered_at",
                "last_launch_status",
                "last_run_workflow_kind",
                "last_run_id",
                "last_job_run_id",
                "last_error_message",
                "updated_at",
            ]
        )
        if run.job.is_terminal:
            notifier = NotificationService()
            if schedule.strategy_template.workflow_kind == StrategyTemplate.WorkflowKind.SCREEN:
                notifier.dispatch_for_screen_run(run)
            else:
                notifier.dispatch_for_backtest_run(run)
        return run


class AlertRuleService:
    def create_rule(self, definition: AlertRuleDefinition) -> AlertRule:
        return AlertRule.objects.create(
            workspace=definition.workspace,
            created_by=definition.created_by,
            strategy_template=definition.strategy_template,
            name=definition.name,
            description=definition.description,
            event_type=definition.event_type,
            workflow_kind=definition.workflow_kind,
            destination_email=definition.destination_email,
            ticker=definition.ticker,
            top_n_threshold=definition.top_n_threshold,
            is_enabled=definition.is_enabled,
        )

    def update_rule(self, rule: AlertRule, **attrs) -> AlertRule:
        for field, value in attrs.items():
            if value is not None:
                setattr(rule, field, value)
        rule.save()
        return rule


class NotificationService:
    def dispatch_for_screen_run(self, screen_run: ScreenRun) -> None:
        screen_run = (
            ScreenRun.objects.select_related("workspace", "workspace__owner", "created_by", "job", "source_template")
            .prefetch_related("result_rows")
            .get(pk=screen_run.pk)
        )
        schedule = self._schedule_for_job(screen_run.job)
        if screen_run.job.state == JobRun.State.SUCCEEDED:
            if schedule and schedule.notify_on_success:
                self._dispatch_schedule_notification(
                    schedule=schedule,
                    screen_run=screen_run,
                    event_type="scheduled_run_succeeded",
                    subject=f"[Greenblatt] Scheduled screen succeeded: {schedule.name}",
                    body=(
                        f"Schedule: {schedule.name}\n"
                        f"Template: {schedule.strategy_template.name}\n"
                        f"Workspace: {screen_run.workspace.name}\n"
                        f"Screen run: #{screen_run.id}\n"
                        f"Results: {screen_run.result_count}\n"
                        f"Top tickers: {', '.join(screen_run.summary.get('top_tickers', [])[:5]) or 'n/a'}"
                    ),
                )
            for rule in self._matching_alert_rules(
                workspace=screen_run.workspace,
                event_type=AlertRule.EventType.SCREEN_COMPLETED,
                workflow_kind=AlertRule.WorkflowKind.SCREEN,
                strategy_template_id=screen_run.source_template_id,
            ):
                self._dispatch_alert_rule_notification(
                    rule=rule,
                    job=screen_run.job,
                    screen_run=screen_run,
                    subject=f"[Greenblatt] Alert triggered: {rule.name}",
                    body=(
                        f"Rule: {rule.name}\n"
                        f"Workspace: {screen_run.workspace.name}\n"
                        f"Screen run: #{screen_run.id}\n"
                        f"Universe: {screen_run.universe.name}\n"
                        f"Results: {screen_run.result_count}\n"
                        f"Top tickers: {', '.join(screen_run.summary.get('top_tickers', [])[:5]) or 'n/a'}"
                    ),
                )
            for rule in self._matching_alert_rules(
                workspace=screen_run.workspace,
                event_type=AlertRule.EventType.TICKER_ENTERED_TOP_N,
                workflow_kind=AlertRule.WorkflowKind.SCREEN,
                strategy_template_id=screen_run.source_template_id,
            ):
                matched_row = screen_run.result_rows.filter(
                    ticker__iexact=rule.ticker,
                    position__lte=rule.top_n_threshold or 0,
                ).order_by("position").first()
                if matched_row is None:
                    continue
                self._dispatch_alert_rule_notification(
                    rule=rule,
                    job=screen_run.job,
                    screen_run=screen_run,
                    subject=f"[Greenblatt] Alert triggered: {rule.ticker} entered top {rule.top_n_threshold}",
                    body=(
                        f"Rule: {rule.name}\n"
                        f"Workspace: {screen_run.workspace.name}\n"
                        f"Screen run: #{screen_run.id}\n"
                        f"Ticker: {matched_row.ticker}\n"
                        f"Position: {matched_row.position}\n"
                        f"Final score: {matched_row.final_score}"
                    ),
                    metadata={"matched_position": matched_row.position, "matched_ticker": matched_row.ticker},
                )
        elif screen_run.job.state in FAILURE_STATES:
            if schedule and schedule.notify_on_failure:
                self._dispatch_schedule_notification(
                    schedule=schedule,
                    screen_run=screen_run,
                    event_type="scheduled_run_failed",
                    subject=f"[Greenblatt] Scheduled screen failed: {schedule.name}",
                    body=(
                        f"Schedule: {schedule.name}\n"
                        f"Template: {schedule.strategy_template.name}\n"
                        f"Workspace: {screen_run.workspace.name}\n"
                        f"Screen run: #{screen_run.id}\n"
                        f"State: {screen_run.job.state}\n"
                        f"Error: {screen_run.job.error_message or 'n/a'}"
                    ),
                )
            for rule in self._matching_alert_rules(
                workspace=screen_run.workspace,
                event_type=AlertRule.EventType.RUN_FAILED,
                workflow_kind=AlertRule.WorkflowKind.SCREEN,
                strategy_template_id=screen_run.source_template_id,
            ):
                self._dispatch_alert_rule_notification(
                    rule=rule,
                    job=screen_run.job,
                    screen_run=screen_run,
                    subject=f"[Greenblatt] Alert triggered: {rule.name}",
                    body=(
                        f"Rule: {rule.name}\n"
                        f"Workspace: {screen_run.workspace.name}\n"
                        f"Screen run: #{screen_run.id}\n"
                        f"State: {screen_run.job.state}\n"
                        f"Error: {screen_run.job.error_message or 'n/a'}"
                    ),
                )
        if schedule is not None:
            self._touch_schedule_terminal_state(schedule, screen_run.job)

    def dispatch_for_backtest_run(self, backtest_run: BacktestRun) -> None:
        backtest_run = BacktestRun.objects.select_related(
            "workspace",
            "workspace__owner",
            "created_by",
            "job",
            "source_template",
            "universe",
        ).get(pk=backtest_run.pk)
        schedule = self._schedule_for_job(backtest_run.job)
        if backtest_run.job.state == JobRun.State.SUCCEEDED:
            if schedule and schedule.notify_on_success:
                self._dispatch_schedule_notification(
                    schedule=schedule,
                    backtest_run=backtest_run,
                    event_type="scheduled_run_succeeded",
                    subject=f"[Greenblatt] Scheduled backtest succeeded: {schedule.name}",
                    body=(
                        f"Schedule: {schedule.name}\n"
                        f"Template: {schedule.strategy_template.name}\n"
                        f"Workspace: {backtest_run.workspace.name}\n"
                        f"Backtest run: #{backtest_run.id}\n"
                        f"Period: {backtest_run.start_date} to {backtest_run.end_date}\n"
                        f"Summary: {backtest_run.summary.get('ending_equity', 'n/a')}"
                    ),
                )
            for rule in self._matching_alert_rules(
                workspace=backtest_run.workspace,
                event_type=AlertRule.EventType.BACKTEST_COMPLETED,
                workflow_kind=AlertRule.WorkflowKind.BACKTEST,
                strategy_template_id=backtest_run.source_template_id,
            ):
                self._dispatch_alert_rule_notification(
                    rule=rule,
                    job=backtest_run.job,
                    backtest_run=backtest_run,
                    subject=f"[Greenblatt] Alert triggered: {rule.name}",
                    body=(
                        f"Rule: {rule.name}\n"
                        f"Workspace: {backtest_run.workspace.name}\n"
                        f"Backtest run: #{backtest_run.id}\n"
                        f"Period: {backtest_run.start_date} to {backtest_run.end_date}\n"
                        f"Ending equity: {backtest_run.summary.get('ending_equity', 'n/a')}"
                    ),
                )
        elif backtest_run.job.state in FAILURE_STATES:
            if schedule and schedule.notify_on_failure:
                self._dispatch_schedule_notification(
                    schedule=schedule,
                    backtest_run=backtest_run,
                    event_type="scheduled_run_failed",
                    subject=f"[Greenblatt] Scheduled backtest failed: {schedule.name}",
                    body=(
                        f"Schedule: {schedule.name}\n"
                        f"Template: {schedule.strategy_template.name}\n"
                        f"Workspace: {backtest_run.workspace.name}\n"
                        f"Backtest run: #{backtest_run.id}\n"
                        f"State: {backtest_run.job.state}\n"
                        f"Error: {backtest_run.job.error_message or 'n/a'}"
                    ),
                )
            for rule in self._matching_alert_rules(
                workspace=backtest_run.workspace,
                event_type=AlertRule.EventType.RUN_FAILED,
                workflow_kind=AlertRule.WorkflowKind.BACKTEST,
                strategy_template_id=backtest_run.source_template_id,
            ):
                self._dispatch_alert_rule_notification(
                    rule=rule,
                    job=backtest_run.job,
                    backtest_run=backtest_run,
                    subject=f"[Greenblatt] Alert triggered: {rule.name}",
                    body=(
                        f"Rule: {rule.name}\n"
                        f"Workspace: {backtest_run.workspace.name}\n"
                        f"Backtest run: #{backtest_run.id}\n"
                        f"State: {backtest_run.job.state}\n"
                        f"Error: {backtest_run.job.error_message or 'n/a'}"
                    ),
                )
        if schedule is not None:
            self._touch_schedule_terminal_state(schedule, backtest_run.job)

    def dispatch_schedule_exception(self, schedule: RunSchedule, exc: Exception) -> NotificationEvent:
        return self._create_and_send_event(
            workspace=schedule.workspace,
            run_schedule=schedule,
            event_type="schedule_dispatch_exception",
            recipient_email=self._schedule_recipient_email(schedule),
            subject=f"[Greenblatt] Scheduled launch failed before dispatch: {schedule.name}",
            body=(
                f"Schedule: {schedule.name}\n"
                f"Template: {schedule.strategy_template.name}\n"
                f"Workspace: {schedule.workspace.name}\n"
                f"Error: {exc}"
            ),
            metadata={"exception_type": exc.__class__.__name__},
        )

    def _matching_alert_rules(
        self,
        *,
        workspace: Workspace,
        event_type: str,
        workflow_kind: str,
        strategy_template_id: int | None,
    ):
        queryset = AlertRule.objects.select_related("workspace", "workspace__owner", "created_by").filter(
            workspace=workspace,
            is_enabled=True,
            event_type=event_type,
        )
        queryset = queryset.filter(Q(workflow_kind=AlertRule.WorkflowKind.ANY) | Q(workflow_kind=workflow_kind))
        if strategy_template_id is None:
            queryset = queryset.filter(strategy_template__isnull=True)
        else:
            queryset = queryset.filter(Q(strategy_template__isnull=True) | Q(strategy_template_id=strategy_template_id))
        return list(queryset)

    def _dispatch_schedule_notification(
        self,
        *,
        schedule: RunSchedule,
        event_type: str,
        subject: str,
        body: str,
        screen_run: ScreenRun | None = None,
        backtest_run: BacktestRun | None = None,
    ) -> NotificationEvent:
        return self._create_and_send_event(
            workspace=schedule.workspace,
            run_schedule=schedule,
            screen_run=screen_run,
            backtest_run=backtest_run,
            job=screen_run.job if screen_run else backtest_run.job if backtest_run else None,
            event_type=event_type,
            recipient_email=self._schedule_recipient_email(schedule),
            subject=subject,
            body=body,
        )

    def _dispatch_alert_rule_notification(
        self,
        *,
        rule: AlertRule,
        job: JobRun,
        subject: str,
        body: str,
        screen_run: ScreenRun | None = None,
        backtest_run: BacktestRun | None = None,
        metadata: dict[str, object] | None = None,
    ) -> NotificationEvent:
        event = self._create_and_send_event(
            workspace=rule.workspace,
            alert_rule=rule,
            screen_run=screen_run,
            backtest_run=backtest_run,
            job=job,
            event_type=rule.event_type,
            recipient_email=self._alert_recipient_email(rule),
            subject=subject,
            body=body,
            metadata=metadata,
        )
        rule.last_triggered_at = timezone.now()
        rule.save(update_fields=["last_triggered_at", "updated_at"])
        return event

    def _create_and_send_event(
        self,
        *,
        workspace: Workspace,
        event_type: str,
        recipient_email: str,
        subject: str,
        body: str,
        alert_rule: AlertRule | None = None,
        run_schedule: RunSchedule | None = None,
        screen_run: ScreenRun | None = None,
        backtest_run: BacktestRun | None = None,
        job: JobRun | None = None,
        metadata: dict[str, object] | None = None,
    ) -> NotificationEvent:
        event = NotificationEvent.objects.create(
            workspace=workspace,
            alert_rule=alert_rule,
            run_schedule=run_schedule,
            screen_run=screen_run,
            backtest_run=backtest_run,
            job=job,
            event_type=event_type,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            metadata=metadata or {},
        )
        return self._deliver_email(event)

    def _deliver_email(self, event: NotificationEvent) -> NotificationEvent:
        if not event.recipient_email:
            event.status = NotificationEvent.Status.SKIPPED
            event.delivery_error = "No recipient email configured."
            event.save(update_fields=["status", "delivery_error", "updated_at"])
            return event
        try:
            sent_count = send_mail(
                event.subject,
                event.body,
                None,
                [event.recipient_email],
                fail_silently=False,
            )
        except Exception as exc:
            logger.exception("Notification %s failed to send", event.pk)
            event.status = NotificationEvent.Status.FAILED
            event.delivery_error = str(exc)
            event.metadata = {**event.metadata, "exception_type": exc.__class__.__name__}
            event.save(update_fields=["status", "delivery_error", "metadata", "updated_at"])
            return event
        event.status = NotificationEvent.Status.SENT if sent_count else NotificationEvent.Status.FAILED
        if not sent_count:
            event.delivery_error = "Email backend returned 0 delivered messages."
        event.sent_at = timezone.now() if sent_count else None
        event.save(update_fields=["status", "delivery_error", "sent_at", "updated_at"])
        return event

    @staticmethod
    def _schedule_for_job(job: JobRun) -> RunSchedule | None:
        schedule_id = job.metadata.get("run_schedule_id")
        if not schedule_id:
            return None
        return RunSchedule.objects.select_related("workspace", "workspace__owner", "created_by", "strategy_template").filter(pk=schedule_id).first()

    @staticmethod
    def _schedule_recipient_email(schedule: RunSchedule) -> str:
        return schedule.notify_email or getattr(schedule.created_by, "email", "") or schedule.workspace.owner.email or ""

    @staticmethod
    def _alert_recipient_email(rule: AlertRule) -> str:
        return rule.destination_email or getattr(rule.created_by, "email", "") or rule.workspace.owner.email or ""

    @staticmethod
    def _touch_schedule_terminal_state(schedule: RunSchedule, job: JobRun) -> None:
        schedule.last_launch_status = job.state
        schedule.last_job_run_id = job.id
        schedule.last_error_message = job.error_message
        schedule.save(update_fields=["last_launch_status", "last_job_run_id", "last_error_message", "updated_at"])
