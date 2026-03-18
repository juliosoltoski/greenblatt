from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.universes.models import Universe
from apps.workspaces.models import Workspace


class StrategyTemplate(models.Model):
    class WorkflowKind(models.TextChoices):
        SCREEN = "screen", "Screen"
        BACKTEST = "backtest", "Backtest"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="strategy_templates")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="strategy_templates",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    workflow_kind = models.CharField(max_length=32, choices=WorkflowKind.choices)
    universe = models.ForeignKey(Universe, on_delete=models.PROTECT, related_name="strategy_templates")
    config = models.JSONField(default=dict, blank=True)
    source_screen_run = models.ForeignKey(
        "screens.ScreenRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saved_templates",
    )
    source_backtest_run = models.ForeignKey(
        "backtests.BacktestRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="saved_templates",
    )
    is_starred = models.BooleanField(default=False)
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "workflow_kind", "updated_at"]),
            models.Index(fields=["workspace", "name"]),
        ]

    def __str__(self) -> str:
        return self.name
