from django.contrib import admin

from apps.screens.models import ScreenExclusion, ScreenResultRow, ScreenRun


class ScreenResultRowInline(admin.TabularInline):
    model = ScreenResultRow
    extra = 0
    can_delete = False
    fields = [
        "position",
        "ticker",
        "final_score",
        "return_on_capital",
        "earnings_yield",
    ]
    readonly_fields = fields
    ordering = ["position"]
    show_change_link = True


class ScreenExclusionInline(admin.TabularInline):
    model = ScreenExclusion
    extra = 0
    can_delete = False
    fields = ["ticker", "reason"]
    readonly_fields = fields
    ordering = ["ticker"]
    show_change_link = True


@admin.register(ScreenRun)
class ScreenRunAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "workspace",
        "universe",
        "job",
        "result_count",
        "exclusion_count",
        "created_at",
    ]
    list_filter = ["workspace", "momentum_mode", "use_cache", "refresh_cache"]
    search_fields = ["id", "workspace__name", "universe__name", "job__celery_task_id"]
    autocomplete_fields = ["workspace", "created_by", "universe", "job"]
    readonly_fields = [
        "summary",
        "result_count",
        "exclusion_count",
        "resolved_ticker_count",
        "total_candidate_count",
        "export_storage_backend",
        "export_storage_key",
        "export_filename",
        "export_checksum_sha256",
        "export_size_bytes",
        "created_at",
        "updated_at",
    ]
    inlines = [ScreenResultRowInline, ScreenExclusionInline]


@admin.register(ScreenResultRow)
class ScreenResultRowAdmin(admin.ModelAdmin):
    list_display = ["screen_run", "position", "ticker", "final_score", "return_on_capital", "earnings_yield"]
    list_filter = ["screen_run__workspace"]
    search_fields = ["ticker", "company_name", "screen_run__id"]
    autocomplete_fields = ["screen_run"]
    readonly_fields = [field.name for field in ScreenResultRow._meta.fields]


@admin.register(ScreenExclusion)
class ScreenExclusionAdmin(admin.ModelAdmin):
    list_display = ["screen_run", "ticker", "reason"]
    list_filter = ["screen_run__workspace", "reason"]
    search_fields = ["ticker", "reason", "screen_run__id"]
    autocomplete_fields = ["screen_run"]
    readonly_fields = [field.name for field in ScreenExclusion._meta.fields]

