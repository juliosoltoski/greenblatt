from __future__ import annotations

from django.conf import settings
from django.db import models
from django_celery_beat.models import PeriodicTask

from apps.jobs.models import JobRun
from apps.strategy_templates.models import StrategyTemplate
from apps.workspaces.models import Workspace


class RunSchedule(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="run_schedules")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="run_schedules",
    )
    strategy_template = models.ForeignKey(StrategyTemplate, on_delete=models.CASCADE, related_name="run_schedules")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    cron_minute = models.CharField(max_length=64, default="0")
    cron_hour = models.CharField(max_length=64, default="13")
    cron_day_of_week = models.CharField(max_length=64, default="1-5")
    cron_day_of_month = models.CharField(max_length=64, default="*")
    cron_month_of_year = models.CharField(max_length=64, default="*")
    is_enabled = models.BooleanField(default=True)
    notify_email = models.EmailField(blank=True)
    notify_on_success = models.BooleanField(default=True)
    notify_on_failure = models.BooleanField(default=True)
    periodic_task = models.OneToOneField(
        PeriodicTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="greenblatt_run_schedule",
    )
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    last_launch_status = models.CharField(max_length=32, blank=True)
    last_run_workflow_kind = models.CharField(max_length=32, blank=True)
    last_run_id = models.PositiveIntegerField(null=True, blank=True)
    last_job_run_id = models.PositiveIntegerField(null=True, blank=True)
    last_error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "is_enabled", "updated_at"]),
            models.Index(fields=["workspace", "strategy_template", "updated_at"]),
        ]

    def __str__(self) -> str:
        return self.name


class AlertRule(models.Model):
    class EventType(models.TextChoices):
        SCREEN_COMPLETED = "screen_completed", "Screen completed"
        BACKTEST_COMPLETED = "backtest_completed", "Backtest completed"
        RUN_FAILED = "run_failed", "Run failed"
        TICKER_ENTERED_TOP_N = "ticker_entered_top_n", "Ticker entered top N"

    class WorkflowKind(models.TextChoices):
        ANY = "", "Any"
        SCREEN = "screen", "Screen"
        BACKTEST = "backtest", "Backtest"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="alert_rules")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alert_rules",
    )
    strategy_template = models.ForeignKey(
        StrategyTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alert_rules",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=64, choices=EventType.choices)
    workflow_kind = models.CharField(max_length=32, choices=WorkflowKind.choices, blank=True, default="")
    channel = models.CharField(max_length=32, choices=Channel.choices, default=Channel.EMAIL)
    destination_email = models.EmailField(blank=True)
    ticker = models.CharField(max_length=32, blank=True)
    top_n_threshold = models.PositiveIntegerField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "event_type", "is_enabled"]),
            models.Index(fields=["workspace", "workflow_kind", "updated_at"]),
        ]

    def __str__(self) -> str:
        return self.name


class NotificationEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="notification_events")
    alert_rule = models.ForeignKey(
        AlertRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_events",
    )
    run_schedule = models.ForeignKey(
        RunSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_events",
    )
    screen_run = models.ForeignKey(
        "screens.ScreenRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_events",
    )
    backtest_run = models.ForeignKey(
        "backtests.BacktestRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_events",
    )
    job = models.ForeignKey(
        JobRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_events",
    )
    channel = models.CharField(max_length=32, choices=Channel.choices, default=Channel.EMAIL)
    event_type = models.CharField(max_length=64)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    recipient_email = models.EmailField(blank=True)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    delivery_error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "status", "created_at"]),
            models.Index(fields=["workspace", "event_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.pk}"
