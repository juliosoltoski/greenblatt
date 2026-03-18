from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.jobs.models import JobRun
from apps.universes.models import Universe
from apps.workspaces.models import Workspace


class BacktestRun(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="backtest_runs")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_backtest_runs",
    )
    source_template = models.ForeignKey(
        "strategy_templates.StrategyTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backtest_runs",
    )
    universe = models.ForeignKey(Universe, on_delete=models.PROTECT, related_name="backtest_runs")
    job = models.OneToOneField(JobRun, on_delete=models.CASCADE, related_name="backtest_run")
    start_date = models.DateField()
    end_date = models.DateField()
    initial_capital = models.FloatField(default=100_000.0)
    portfolio_size = models.PositiveIntegerField(default=20)
    review_frequency = models.CharField(max_length=32, default="W-FRI")
    benchmark = models.CharField(max_length=32, default="^GSPC", blank=True)
    momentum_mode = models.CharField(max_length=16, default="none")
    sector_allowlist = models.JSONField(default=list, blank=True)
    min_market_cap = models.FloatField(null=True, blank=True)
    use_cache = models.BooleanField(default=True)
    refresh_cache = models.BooleanField(default=False)
    cache_ttl_hours = models.FloatField(default=24.0)
    equity_point_count = models.PositiveIntegerField(default=0)
    trade_count = models.PositiveIntegerField(default=0)
    review_target_count = models.PositiveIntegerField(default=0)
    final_holding_count = models.PositiveIntegerField(default=0)
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
        return f"backtest#{self.pk}"

    @property
    def has_export(self) -> bool:
        return bool(self.export_storage_key)


class BacktestEquityPoint(models.Model):
    backtest_run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="equity_points")
    position = models.PositiveIntegerField()
    date = models.DateField()
    cash = models.FloatField()
    equity = models.FloatField()
    positions = models.PositiveIntegerField()
    benchmark_equity = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["backtest_run", "position"], name="uniq_backtest_equity_position"),
            models.UniqueConstraint(fields=["backtest_run", "date"], name="uniq_backtest_equity_date"),
        ]

    def __str__(self) -> str:
        return f"{self.backtest_run_id}:{self.position}"


class BacktestTrade(models.Model):
    backtest_run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="trades")
    position = models.PositiveIntegerField()
    date = models.DateField()
    ticker = models.CharField(max_length=32)
    side = models.CharField(max_length=8)
    shares = models.FloatField()
    price = models.FloatField()
    proceeds = models.FloatField()
    reason = models.CharField(max_length=255)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["backtest_run", "position"], name="uniq_backtest_trade_position"),
        ]
        indexes = [
            models.Index(fields=["backtest_run", "date"]),
            models.Index(fields=["backtest_run", "ticker"]),
        ]

    def __str__(self) -> str:
        return f"{self.backtest_run_id}:{self.position}:{self.ticker}"


class BacktestReviewTarget(models.Model):
    backtest_run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="review_targets")
    position = models.PositiveIntegerField()
    date = models.DateField()
    target_rank = models.PositiveIntegerField()
    ticker = models.CharField(max_length=32)
    company_name = models.CharField(max_length=255, blank=True)
    sector = models.CharField(max_length=255, blank=True)
    industry = models.CharField(max_length=255, blank=True)
    final_score = models.PositiveIntegerField(null=True, blank=True)
    composite_score = models.PositiveIntegerField(null=True, blank=True)
    roc_rank = models.PositiveIntegerField(null=True, blank=True)
    ey_rank = models.PositiveIntegerField(null=True, blank=True)
    momentum_rank = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["backtest_run", "position"], name="uniq_backtest_review_position"),
        ]
        indexes = [
            models.Index(fields=["backtest_run", "date"]),
            models.Index(fields=["backtest_run", "ticker"]),
        ]

    def __str__(self) -> str:
        return f"{self.backtest_run_id}:{self.position}:{self.ticker}"


class BacktestFinalHolding(models.Model):
    backtest_run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="final_holdings")
    position = models.PositiveIntegerField()
    ticker = models.CharField(max_length=32)
    shares = models.FloatField()
    entry_date = models.DateField()
    entry_price = models.FloatField()
    score = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["backtest_run", "position"], name="uniq_backtest_holding_position"),
            models.UniqueConstraint(fields=["backtest_run", "ticker"], name="uniq_backtest_holding_ticker"),
        ]

    def __str__(self) -> str:
        return f"{self.backtest_run_id}:{self.ticker}"
