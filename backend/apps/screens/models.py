from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.jobs.models import JobRun
from apps.universes.models import Universe
from apps.workspaces.models import Workspace


class ScreenRun(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="screen_runs")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_screen_runs",
    )
    source_template = models.ForeignKey(
        "strategy_templates.StrategyTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="screen_runs",
    )
    universe = models.ForeignKey(Universe, on_delete=models.PROTECT, related_name="screen_runs")
    job = models.OneToOneField(JobRun, on_delete=models.CASCADE, related_name="screen_run")
    top_n = models.PositiveIntegerField(default=30)
    momentum_mode = models.CharField(max_length=16, default="none")
    sector_allowlist = models.JSONField(default=list, blank=True)
    min_market_cap = models.FloatField(null=True, blank=True)
    exclude_financials = models.BooleanField(default=True)
    exclude_utilities = models.BooleanField(default=True)
    exclude_adrs = models.BooleanField(default=True)
    use_cache = models.BooleanField(default=True)
    refresh_cache = models.BooleanField(default=False)
    cache_ttl_hours = models.FloatField(default=24.0)
    result_count = models.PositiveIntegerField(default=0)
    exclusion_count = models.PositiveIntegerField(default=0)
    resolved_ticker_count = models.PositiveIntegerField(default=0)
    total_candidate_count = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    export_storage_backend = models.CharField(max_length=50, blank=True)
    export_storage_key = models.CharField(max_length=500, blank=True)
    export_filename = models.CharField(max_length=255, blank=True)
    export_checksum_sha256 = models.CharField(max_length=64, blank=True)
    export_size_bytes = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["workspace", "created_at"]),
            models.Index(fields=["universe", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"screen#{self.pk}"

    @property
    def has_export(self) -> bool:
        return bool(self.export_storage_key)


class ScreenResultRow(models.Model):
    screen_run = models.ForeignKey(ScreenRun, on_delete=models.CASCADE, related_name="result_rows")
    position = models.PositiveIntegerField()
    ticker = models.CharField(max_length=32)
    company_name = models.CharField(max_length=255, blank=True)
    sector = models.CharField(max_length=255, blank=True)
    industry = models.CharField(max_length=255, blank=True)
    market_cap = models.FloatField(null=True, blank=True)
    ebit = models.FloatField(null=True, blank=True)
    net_working_capital = models.FloatField(null=True, blank=True)
    enterprise_value = models.FloatField(null=True, blank=True)
    return_on_capital = models.FloatField(null=True, blank=True)
    earnings_yield = models.FloatField(null=True, blank=True)
    momentum_6m = models.FloatField(null=True, blank=True)
    roc_rank = models.PositiveIntegerField(null=True, blank=True)
    ey_rank = models.PositiveIntegerField(null=True, blank=True)
    momentum_rank = models.PositiveIntegerField(null=True, blank=True)
    composite_score = models.PositiveIntegerField(null=True, blank=True)
    final_score = models.PositiveIntegerField(null=True, blank=True)
    row_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["screen_run", "position"], name="uniq_screen_result_row_position"),
            models.UniqueConstraint(fields=["screen_run", "ticker"], name="uniq_screen_result_row_ticker"),
        ]

    def __str__(self) -> str:
        return f"{self.screen_run_id}:{self.position}:{self.ticker}"


class ScreenExclusion(models.Model):
    screen_run = models.ForeignKey(ScreenRun, on_delete=models.CASCADE, related_name="exclusions")
    ticker = models.CharField(max_length=32)
    reason = models.CharField(max_length=255)

    class Meta:
        ordering = ["ticker", "id"]
        indexes = [
            models.Index(fields=["screen_run", "ticker"]),
        ]

    def __str__(self) -> str:
        return f"{self.screen_run_id}:{self.ticker}"
