from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("workspaces", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("job_type", models.CharField(db_index=True, max_length=64)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                            ("partial_failed", "Partial failed"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=32,
                    ),
                ),
                ("progress_percent", models.PositiveSmallIntegerField(default=0)),
                ("current_step", models.CharField(blank=True, max_length=255)),
                ("error_code", models.CharField(blank=True, max_length=100)),
                ("error_message", models.TextField(blank=True)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("celery_task_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="jobs",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="jobrun",
            index=models.Index(fields=["workspace", "created_at"], name="jobs_jobrun_workspa_3d8b17_idx"),
        ),
        migrations.AddIndex(
            model_name="jobrun",
            index=models.Index(fields=["workspace", "state"], name="jobs_jobrun_workspa_ddd632_idx"),
        ),
    ]
