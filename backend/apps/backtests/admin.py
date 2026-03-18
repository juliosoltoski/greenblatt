from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin
from apps.backtests.models import (
    BacktestEquityPoint,
    BacktestFinalHolding,
    BacktestReviewTarget,
    BacktestRun,
    BacktestTrade,
)


class BacktestEquityPointInline(admin.TabularInline):
    model = BacktestEquityPoint
    extra = 0
    can_delete = False
    fields = ["position", "date", "equity", "benchmark_equity", "positions"]
    readonly_fields = fields
    ordering = ["position"]


class BacktestTradeInline(admin.TabularInline):
    model = BacktestTrade
    extra = 0
    can_delete = False
    fields = ["position", "date", "ticker", "side", "shares", "price", "reason"]
    readonly_fields = fields
    ordering = ["position"]
    show_change_link = True


class BacktestFinalHoldingInline(admin.TabularInline):
    model = BacktestFinalHolding
    extra = 0
    can_delete = False
    fields = ["position", "ticker", "shares", "entry_date", "entry_price", "score"]
    readonly_fields = fields
    ordering = ["position"]
    show_change_link = True


@admin.register(BacktestRun)
class BacktestRunAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "workspace",
        "universe",
        "job",
        "start_date",
        "end_date",
        "trade_count",
        "final_holding_count",
        "created_at",
    ]
    list_filter = ["workspace", "momentum_mode", "benchmark", "use_cache", "refresh_cache"]
    search_fields = ["id", "workspace__name", "universe__name", "job__celery_task_id"]
    autocomplete_fields = ["workspace", "created_by", "universe", "job"]
    readonly_fields = [
        "summary",
        "equity_point_count",
        "trade_count",
        "review_target_count",
        "final_holding_count",
        "export_storage_backend",
        "export_storage_key",
        "export_filename",
        "export_checksum_sha256",
        "export_size_bytes",
        "created_at",
        "updated_at",
    ]
    inlines = [BacktestEquityPointInline, BacktestTradeInline, BacktestFinalHoldingInline]


@admin.register(BacktestEquityPoint)
class BacktestEquityPointAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["backtest_run", "position", "date", "equity", "benchmark_equity", "positions"]
    search_fields = ["backtest_run__id"]
    autocomplete_fields = ["backtest_run"]
    readonly_fields = [field.name for field in BacktestEquityPoint._meta.fields]


@admin.register(BacktestTrade)
class BacktestTradeAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["backtest_run", "position", "date", "ticker", "side", "shares", "price", "reason"]
    list_filter = ["side", "reason", "backtest_run__workspace"]
    search_fields = ["ticker", "reason", "backtest_run__id"]
    autocomplete_fields = ["backtest_run"]
    readonly_fields = [field.name for field in BacktestTrade._meta.fields]


@admin.register(BacktestReviewTarget)
class BacktestReviewTargetAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["backtest_run", "date", "target_rank", "ticker", "final_score"]
    list_filter = ["backtest_run__workspace"]
    search_fields = ["ticker", "backtest_run__id"]
    autocomplete_fields = ["backtest_run"]
    readonly_fields = [field.name for field in BacktestReviewTarget._meta.fields]


@admin.register(BacktestFinalHolding)
class BacktestFinalHoldingAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["backtest_run", "position", "ticker", "shares", "entry_date", "entry_price", "score"]
    list_filter = ["backtest_run__workspace"]
    search_fields = ["ticker", "backtest_run__id"]
    autocomplete_fields = ["backtest_run"]
    readonly_fields = [field.name for field in BacktestFinalHolding._meta.fields]
