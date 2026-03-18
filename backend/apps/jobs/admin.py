from django.contrib import admin

from apps.jobs.models import JobRun


@admin.register(JobRun)
class JobRunAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "job_type",
        "workspace",
        "state",
        "progress_percent",
        "retry_count",
        "celery_task_id",
        "created_at",
        "finished_at",
    ]
    list_filter = ["job_type", "state", "workspace"]
    search_fields = [
        "id",
        "job_type",
        "workspace__name",
        "workspace__slug",
        "celery_task_id",
        "error_code",
        "error_message",
    ]
    autocomplete_fields = ["workspace", "created_by"]
    readonly_fields = [
        "state",
        "progress_percent",
        "current_step",
        "error_code",
        "error_message",
        "retry_count",
        "celery_task_id",
        "metadata",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    ]
