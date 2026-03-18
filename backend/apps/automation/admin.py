from django.contrib import admin

from apps.automation.models import AlertRule, NotificationEvent, RunSchedule


@admin.register(RunSchedule)
class RunScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "workspace",
        "strategy_template",
        "is_enabled",
        "timezone",
        "last_launch_status",
        "updated_at",
    )
    list_filter = ("is_enabled", "timezone", "strategy_template__workflow_kind")
    search_fields = ("name", "description", "workspace__name", "strategy_template__name")
    autocomplete_fields = ("workspace", "created_by", "strategy_template", "periodic_task")


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "workspace", "event_type", "workflow_kind", "is_enabled", "last_triggered_at")
    list_filter = ("event_type", "workflow_kind", "is_enabled")
    search_fields = ("name", "description", "workspace__name", "ticker", "destination_email")
    autocomplete_fields = ("workspace", "created_by", "strategy_template")


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "workspace", "status", "recipient_email", "created_at", "sent_at")
    list_filter = ("event_type", "status", "channel")
    search_fields = ("subject", "recipient_email", "workspace__name", "delivery_error")
    autocomplete_fields = ("workspace", "alert_rule", "run_schedule", "screen_run", "backtest_run", "job")
