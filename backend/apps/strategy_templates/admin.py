from django.contrib import admin

from apps.strategy_templates.models import StrategyTemplate


@admin.register(StrategyTemplate)
class StrategyTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "workflow_kind",
        "workspace",
        "universe",
        "created_by",
        "last_used_at",
        "updated_at",
    ]
    list_filter = ["workflow_kind", "workspace"]
    search_fields = ["name", "description", "universe__name"]
    autocomplete_fields = ["workspace", "universe", "created_by", "source_screen_run", "source_backtest_run"]
    readonly_fields = ["created_at", "updated_at", "last_used_at"]

