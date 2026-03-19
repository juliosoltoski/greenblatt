from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.workspaces.models import Workspace


class JobRun(models.Model):
    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        PARTIAL_FAILED = "partial_failed", "Partial failed"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="jobs")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_jobs",
    )
    job_type = models.CharField(max_length=64, db_index=True)
    state = models.CharField(max_length=32, choices=State.choices, default=State.QUEUED, db_index=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    current_step = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)
    cancel_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancel_requested_jobs",
    )
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "created_at"]),
            models.Index(fields=["workspace", "state"]),
        ]

    def __str__(self) -> str:
        return f"{self.job_type}#{self.pk}"

    @property
    def is_terminal(self) -> bool:
        return self.state in {
            self.State.SUCCEEDED,
            self.State.FAILED,
            self.State.CANCELLED,
            self.State.PARTIAL_FAILED,
        }

    @property
    def queue_latency_seconds(self) -> float | None:
        if self.started_at is None:
            return None
        return max(0.0, (self.started_at - self.created_at).total_seconds())

    @property
    def run_duration_seconds(self) -> float | None:
        if self.started_at is None or self.finished_at is None:
            return None
        return max(0.0, (self.finished_at - self.started_at).total_seconds())

    @property
    def cancellation_requested(self) -> bool:
        return self.cancel_requested_at is not None and not self.is_terminal


class JobEvent(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="job_events")
    job = models.ForeignKey(JobRun, on_delete=models.CASCADE, related_name="events")
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.INFO)
    event_type = models.CharField(max_length=64)
    message = models.CharField(max_length=255)
    progress_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["workspace", "job", "created_at"]),
            models.Index(fields=["job", "event_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.job_id}:{self.event_type}:{self.pk}"
