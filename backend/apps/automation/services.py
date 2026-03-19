from __future__ import annotations

import json
import logging
from datetime import timedelta
from dataclasses import dataclass
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.core.mail import send_mail
from django.db.models import Count
from django.db import transaction
from django.db.models import Q
from django.template.defaultfilters import slugify
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from apps.automation.models import AlertRule, NotificationEvent, RunSchedule, UserNotificationPreference, WorkspaceNotificationPreference
from apps.backtests.models import BacktestRun
from apps.jobs.models import JobEvent, JobRun
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

DIGEST_PERIODIC_TASK_NAME = "greenblatt-send-notification-digests-hourly"


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
    notify_channel: str
    notify_email: str
    notify_webhook_url: str
    notify_on_success: bool
    notify_on_failure: bool
    review_status: str
    review_notes: str


@dataclass(frozen=True, slots=True)
class AlertRuleDefinition:
    workspace: Workspace
    created_by: object
    name: str
    description: str
    event_type: str
    workflow_kind: str
    channel: str
    destination_email: str
    destination_webhook_url: str
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
                notify_channel=definition.notify_channel,
                notify_email=definition.notify_email,
                notify_webhook_url=definition.notify_webhook_url,
                notify_on_success=definition.notify_on_success,
                notify_on_failure=definition.notify_on_failure,
                review_status=definition.review_status,
                review_notes=definition.review_notes,
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
            channel=definition.channel,
            destination_email=definition.destination_email,
            destination_webhook_url=definition.destination_webhook_url,
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
    def sync_system_tasks(self) -> PeriodicTask:
        crontab, _ = CrontabSchedule.objects.get_or_create(
            minute="5",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )
        task, _ = PeriodicTask.objects.get_or_create(
            name=DIGEST_PERIODIC_TASK_NAME,
            defaults={
                "task": "automation.send_notification_digests",
                "crontab": crontab,
                "kwargs": "{}",
                "enabled": True,
                "one_off": False,
                "description": "Dispatch workspace notification digests.",
            },
        )
        changed = False
        if task.task != "automation.send_notification_digests":
            task.task = "automation.send_notification_digests"
            changed = True
        if task.crontab_id != crontab.id:
            task.crontab = crontab
            changed = True
        if task.kwargs != "{}":
            task.kwargs = "{}"
            changed = True
        if not task.enabled:
            task.enabled = True
            changed = True
        if task.one_off:
            task.one_off = False
            changed = True
        description = "Dispatch workspace notification digests."
        if task.description != description:
            task.description = description
            changed = True
        if changed:
            task.save()
        return task

    def workspace_preferences(self, workspace: Workspace) -> WorkspaceNotificationPreference:
        preference, _ = WorkspaceNotificationPreference.objects.get_or_create(
            workspace=workspace,
            defaults={"default_email": workspace.owner.email},
        )
        self.sync_system_tasks()
        return preference

    def user_preferences(self, workspace: Workspace, user) -> UserNotificationPreference | None:
        if user is None:
            return None
        preference, _ = UserNotificationPreference.objects.get_or_create(
            workspace=workspace,
            user=user,
            defaults={"delivery_email": user.email, "slack_enabled": True, "webhook_enabled": True},
        )
        return preference

    def dispatch_pending_digests(self, *, now=None) -> int:
        now = now or timezone.now()
        sent_count = 0
        preferences = (
            WorkspaceNotificationPreference.objects.select_related("workspace", "workspace__owner")
            .filter(digest_enabled=True, digest_hour_utc=now.hour)
            .order_by("workspace_id")
        )
        for workspace_preference in preferences:
            sent_count += self.dispatch_workspace_digest(
                workspace_preference.workspace,
                workspace_preference=workspace_preference,
                now=now,
            )
        return sent_count

    def dispatch_workspace_digest(
        self,
        workspace: Workspace,
        *,
        workspace_preference: WorkspaceNotificationPreference | None = None,
        now=None,
    ) -> int:
        now = now or timezone.now()
        workspace_preference = workspace_preference or self.workspace_preferences(workspace)
        if not workspace_preference.digest_enabled:
            return 0
        if workspace_preference.last_digest_sent_at and workspace_preference.last_digest_sent_at.date() == now.date():
            return 0

        since = workspace_preference.last_digest_sent_at or (now - timedelta(days=1))
        digest_payload = self._build_digest_payload(workspace=workspace, since=since, now=now)
        recipients = self._digest_recipients(workspace=workspace, workspace_preference=workspace_preference)
        if digest_payload["total_runs"] == 0 or not recipients:
            workspace_preference.last_digest_sent_at = now
            workspace_preference.save(update_fields=["last_digest_sent_at", "updated_at"])
            return 0

        subject = f"[Greenblatt] Workspace digest: {workspace.name}"
        body = self._format_digest_body(
            workspace=workspace,
            since=since,
            now=now,
            payload=digest_payload,
        )
        sent_count = 0
        for recipient in recipients:
            event = self._create_and_send_event(
                workspace=workspace,
                event_type="workspace_digest",
                channel=NotificationEvent.Channel.DIGEST,
                recipient_email=recipient["email"],
                subject=subject,
                body=body,
                metadata={
                    **digest_payload,
                    "window_start": since.isoformat(),
                    "window_end": now.isoformat(),
                    "recipient_user_id": recipient.get("user_id"),
                },
                actor=recipient.get("user"),
            )
            if event.status == NotificationEvent.Status.SENT:
                sent_count += 1
        workspace_preference.last_digest_sent_at = now
        workspace_preference.save(update_fields=["last_digest_sent_at", "updated_at"])
        return sent_count

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
                    channel=schedule.notify_channel,
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
                    channel=schedule.notify_channel,
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
                    channel=schedule.notify_channel,
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
                    channel=schedule.notify_channel,
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
            channel=schedule.notify_channel,
            recipient_email=self._schedule_recipient_email(schedule),
            recipient_webhook_url=schedule.notify_webhook_url,
            subject=f"[Greenblatt] Scheduled launch failed before dispatch: {schedule.name}",
            body=(
                f"Schedule: {schedule.name}\n"
                f"Template: {schedule.strategy_template.name}\n"
                f"Workspace: {schedule.workspace.name}\n"
                f"Error: {exc}"
            ),
            metadata={"exception_type": exc.__class__.__name__},
            actor=schedule.created_by,
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
        channel: str,
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
            channel=channel,
            recipient_email=self._schedule_recipient_email(schedule),
            recipient_webhook_url=schedule.notify_webhook_url,
            subject=subject,
            body=body,
            actor=schedule.created_by,
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
            channel=rule.channel,
            recipient_email=self._alert_recipient_email(rule),
            recipient_webhook_url=rule.destination_webhook_url,
            subject=subject,
            body=body,
            metadata=metadata,
            actor=rule.created_by,
        )
        rule.last_triggered_at = timezone.now()
        rule.save(update_fields=["last_triggered_at", "updated_at"])
        return event

    def _create_and_send_event(
        self,
        *,
        workspace: Workspace,
        event_type: str,
        channel: str,
        recipient_email: str,
        recipient_webhook_url: str = "",
        subject: str,
        body: str,
        alert_rule: AlertRule | None = None,
        run_schedule: RunSchedule | None = None,
        screen_run: ScreenRun | None = None,
        backtest_run: BacktestRun | None = None,
        job: JobRun | None = None,
        metadata: dict[str, object] | None = None,
        actor=None,
    ) -> NotificationEvent:
        workspace_preference = self.workspace_preferences(workspace)
        user_preference = self.user_preferences(workspace, actor)
        resolved_email = self._resolved_email(
            recipient_email=recipient_email,
            workspace=workspace,
            workspace_preference=workspace_preference,
            user_preference=user_preference,
        )
        resolved_webhook_url = self._resolved_webhook_url(
            channel=channel,
            recipient_webhook_url=recipient_webhook_url,
            workspace_preference=workspace_preference,
        )
        event = NotificationEvent.objects.create(
            workspace=workspace,
            alert_rule=alert_rule,
            run_schedule=run_schedule,
            screen_run=screen_run,
            backtest_run=backtest_run,
            job=job,
            channel=channel,
            event_type=event_type,
            recipient_email=resolved_email,
            recipient_webhook_url=resolved_webhook_url,
            subject=subject,
            body=body,
            metadata=metadata or {},
        )
        if not self._channel_is_enabled(channel, workspace_preference, user_preference):
            event.status = NotificationEvent.Status.SKIPPED
            event.delivery_error = "Notification channel is disabled by preferences."
            event.save(update_fields=["status", "delivery_error", "updated_at"])
            return event
        return self._deliver(event)

    def _deliver(self, event: NotificationEvent) -> NotificationEvent:
        try:
            if event.channel in {NotificationEvent.Channel.EMAIL, NotificationEvent.Channel.DIGEST}:
                if not event.recipient_email:
                    raise RuntimeError("No recipient email configured.")
                sent_count = send_mail(
                    event.subject,
                    event.body,
                    None,
                    [event.recipient_email],
                    fail_silently=False,
                )
            elif event.channel in {NotificationEvent.Channel.SLACK_WEBHOOK, NotificationEvent.Channel.WEBHOOK}:
                if not event.recipient_webhook_url:
                    raise RuntimeError("No webhook destination configured.")
                self._send_webhook(event)
                sent_count = 1
            else:
                raise RuntimeError(f"Unsupported notification channel '{event.channel}'.")
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
    def _channel_is_enabled(
        channel: str,
        workspace_preference: WorkspaceNotificationPreference,
        user_preference: UserNotificationPreference | None,
    ) -> bool:
        if channel == NotificationEvent.Channel.EMAIL:
            return workspace_preference.email_enabled and (user_preference.email_enabled if user_preference else True)
        if channel == NotificationEvent.Channel.SLACK_WEBHOOK:
            return workspace_preference.slack_enabled and (user_preference.slack_enabled if user_preference else True)
        if channel == NotificationEvent.Channel.WEBHOOK:
            return workspace_preference.webhook_enabled and (user_preference.webhook_enabled if user_preference else True)
        if channel == NotificationEvent.Channel.DIGEST:
            return (
                workspace_preference.digest_enabled
                and workspace_preference.email_enabled
                and (user_preference.digest_enabled if user_preference else True)
                and (user_preference.email_enabled if user_preference else True)
            )
        return True

    @staticmethod
    def _resolved_email(
        *,
        recipient_email: str,
        workspace: Workspace,
        workspace_preference: WorkspaceNotificationPreference,
        user_preference: UserNotificationPreference | None,
    ) -> str:
        return (
            recipient_email
            or (user_preference.delivery_email if user_preference else "")
            or workspace_preference.default_email
            or workspace.owner.email
            or ""
        )

    @staticmethod
    def _resolved_webhook_url(
        *,
        channel: str,
        recipient_webhook_url: str,
        workspace_preference: WorkspaceNotificationPreference,
    ) -> str:
        if recipient_webhook_url:
            return recipient_webhook_url
        if channel == NotificationEvent.Channel.SLACK_WEBHOOK:
            return workspace_preference.slack_webhook_url
        if channel == NotificationEvent.Channel.WEBHOOK:
            return workspace_preference.generic_webhook_url
        return ""

    @staticmethod
    def _send_webhook(event: NotificationEvent) -> None:
        if event.channel == NotificationEvent.Channel.SLACK_WEBHOOK:
            payload = {"text": f"{event.subject}\n{event.body}"}
        else:
            payload = {
                "subject": event.subject,
                "body": event.body,
                "event_type": event.event_type,
                "metadata": event.metadata,
            }
        request = urllib_request.Request(
            event.recipient_webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib_request.urlopen(request, timeout=10) as response:
                status_code = getattr(response, "status", 200)
        except urllib_error.URLError as exc:
            raise RuntimeError(f"Webhook delivery failed: {exc.reason}") from exc
        if status_code >= 400:
            raise RuntimeError(f"Webhook delivery failed with status {status_code}.")

    @staticmethod
    def _schedule_for_job(job: JobRun) -> RunSchedule | None:
        schedule_id = job.metadata.get("run_schedule_id")
        if not schedule_id:
            return None
        return RunSchedule.objects.select_related("workspace", "workspace__owner", "created_by", "strategy_template").filter(pk=schedule_id).first()

    def _build_digest_payload(self, *, workspace: Workspace, since, now) -> dict[str, object]:
        screen_runs = list(
            ScreenRun.objects.select_related("job", "universe", "source_template")
            .filter(workspace=workspace, job__finished_at__gt=since, job__finished_at__lte=now)
            .order_by("-job__finished_at", "-id")
        )
        backtest_runs = list(
            BacktestRun.objects.select_related("job", "universe", "source_template")
            .filter(workspace=workspace, job__finished_at__gt=since, job__finished_at__lte=now)
            .order_by("-job__finished_at", "-id")
        )
        run_items: list[dict[str, object]] = []
        for screen_run in screen_runs:
            run_items.append(
                {
                    "workflow_kind": "screen",
                    "run_id": screen_run.id,
                    "job_state": screen_run.job.state,
                    "finished_at": screen_run.job.finished_at.isoformat() if screen_run.job.finished_at else None,
                    "template_name": screen_run.source_template.name if screen_run.source_template else "manual launch",
                    "universe_name": screen_run.universe.name,
                    "summary": f"{screen_run.result_count} results",
                }
            )
        for backtest_run in backtest_runs:
            ending_equity = backtest_run.summary.get("ending_equity", "n/a")
            run_items.append(
                {
                    "workflow_kind": "backtest",
                    "run_id": backtest_run.id,
                    "job_state": backtest_run.job.state,
                    "finished_at": backtest_run.job.finished_at.isoformat() if backtest_run.job.finished_at else None,
                    "template_name": backtest_run.source_template.name if backtest_run.source_template else "manual launch",
                    "universe_name": backtest_run.universe.name,
                    "summary": f"ending equity {ending_equity}",
                }
            )
        run_items.sort(key=lambda item: str(item.get("finished_at") or ""), reverse=True)

        state_counts = {
            state: sum(1 for item in run_items if item["job_state"] == state)
            for state in [
                JobRun.State.SUCCEEDED,
                JobRun.State.FAILED,
                JobRun.State.CANCELLED,
                JobRun.State.PARTIAL_FAILED,
            ]
        }
        notification_counts = {
            entry["status"]: entry["count"]
            for entry in NotificationEvent.objects.filter(workspace=workspace, created_at__gt=since, created_at__lte=now)
            .exclude(channel=NotificationEvent.Channel.DIGEST)
            .values("status")
            .annotate(count=Count("id"))
        }
        provider_failure_count = JobEvent.objects.filter(
            workspace=workspace,
            created_at__gt=since,
            created_at__lte=now,
            event_type="provider_failure",
        ).count()
        return {
            "total_runs": len(run_items),
            "state_counts": state_counts,
            "notification_counts": notification_counts,
            "provider_failure_count": provider_failure_count,
            "recent_runs": run_items[:10],
        }

    def _format_digest_body(self, *, workspace: Workspace, since, now, payload: dict[str, object]) -> str:
        state_counts = payload["state_counts"]
        notification_counts = payload["notification_counts"]
        recent_runs = payload["recent_runs"]
        lines = [
            f"Workspace: {workspace.name}",
            f"Window: {since.isoformat()} to {now.isoformat()}",
            "",
            (
                "Runs: "
                f"{payload['total_runs']} total | "
                f"{state_counts.get(JobRun.State.SUCCEEDED, 0)} succeeded | "
                f"{state_counts.get(JobRun.State.FAILED, 0)} failed | "
                f"{state_counts.get(JobRun.State.CANCELLED, 0)} cancelled | "
                f"{state_counts.get(JobRun.State.PARTIAL_FAILED, 0)} partial_failed"
            ),
            (
                "Notifications: "
                f"{notification_counts.get(NotificationEvent.Status.SENT, 0)} sent | "
                f"{notification_counts.get(NotificationEvent.Status.FAILED, 0)} failed | "
                f"{notification_counts.get(NotificationEvent.Status.SKIPPED, 0)} skipped"
            ),
        ]
        if payload["provider_failure_count"]:
            lines.append(f"Provider failures observed: {payload['provider_failure_count']}")
        lines.append("")
        if not recent_runs:
            lines.append("No completed screen or backtest runs were recorded in this window.")
            return "\n".join(lines)
        lines.append("Recent runs:")
        for run in recent_runs:
            lines.append(
                f"- {run['workflow_kind']} #{run['run_id']} | {run['job_state']} | "
                f"{run['template_name']} | {run['universe_name']} | {run['summary']}"
            )
        return "\n".join(lines)

    def _digest_recipients(
        self,
        *,
        workspace: Workspace,
        workspace_preference: WorkspaceNotificationPreference,
    ) -> list[dict[str, object]]:
        user_preferences = list(
            UserNotificationPreference.objects.select_related("user")
            .filter(workspace=workspace, digest_enabled=True, email_enabled=True)
            .order_by("user_id")
        )
        recipients: list[dict[str, object]] = []
        for user_preference in user_preferences:
            email = (
                user_preference.delivery_email
                or getattr(user_preference.user, "email", "")
                or workspace_preference.default_email
                or workspace.owner.email
            )
            if not email:
                continue
            recipients.append(
                {
                    "user": user_preference.user,
                    "user_id": user_preference.user_id,
                    "email": email,
                }
            )
        if recipients:
            return recipients
        if workspace_preference.email_enabled and workspace_preference.default_email:
            return [{"user": None, "user_id": None, "email": workspace_preference.default_email}]
        if workspace_preference.email_enabled and workspace.owner.email:
            return [{"user": workspace.owner, "user_id": workspace.owner_id, "email": workspace.owner.email}]
        return []

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
