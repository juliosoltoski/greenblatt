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
            name="UniverseUpload",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_filename", models.CharField(max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=255)),
                ("storage_backend", models.CharField(default="filesystem", max_length=50)),
                ("storage_key", models.CharField(max_length=500, unique=True)),
                ("checksum_sha256", models.CharField(max_length=64)),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="universe_uploads",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="universe_uploads",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="Universe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                (
                    "source_type",
                    models.CharField(
                        choices=[("built_in", "Built-in"), ("manual", "Manual"), ("uploaded_file", "Uploaded file")],
                        max_length=32,
                    ),
                ),
                ("profile_key", models.CharField(blank=True, max_length=100)),
                ("entry_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_universes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_upload",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_universes",
                        to="universes.universeupload",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="universes",
                        to="workspaces.workspace",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
        migrations.CreateModel(
            name="UniverseEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField()),
                ("raw_ticker", models.CharField(max_length=32)),
                ("normalized_ticker", models.CharField(max_length=32)),
                ("inclusion_metadata", models.JSONField(blank=True, default=dict)),
                (
                    "universe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="entries",
                        to="universes.universe",
                    ),
                ),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddConstraint(
            model_name="universeentry",
            constraint=models.UniqueConstraint(fields=("universe", "position"), name="uniq_universe_entry_position"),
        ),
        migrations.AddConstraint(
            model_name="universeentry",
            constraint=models.UniqueConstraint(fields=("universe", "normalized_ticker"), name="uniq_universe_entry_ticker"),
        ),
    ]
