from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.backtests.models import BacktestRun
from apps.screens.models import ScreenRun
from apps.universes.models import UniverseUpload


class Command(BaseCommand):
    help = "Delete orphaned filesystem artifacts older than the configured cutoff."

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-hours",
            type=float,
            default=getattr(settings, "ARTIFACT_ORPHAN_RETENTION_HOURS", 24.0),
            help="Only delete orphaned files older than this many hours.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List orphaned artifacts without deleting them.",
        )

    def handle(self, *args, **options):
        if settings.ARTIFACT_STORAGE_BACKEND != "filesystem":
            raise CommandError("cleanup_artifacts only supports the filesystem artifact backend.")

        root = Path(settings.ARTIFACT_STORAGE_ROOT)
        if not root.exists():
            self.stdout.write("Artifact root does not exist. Nothing to clean.")
            return

        cutoff = datetime.now(UTC) - timedelta(hours=options["older_than_hours"])
        referenced = {
            *UniverseUpload.objects.exclude(storage_key="").values_list("storage_key", flat=True),
            *ScreenRun.objects.exclude(export_storage_key="").values_list("export_storage_key", flat=True),
            *BacktestRun.objects.exclude(export_storage_key="").values_list("export_storage_key", flat=True),
        }

        orphaned_files: list[Path] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative_key = path.relative_to(root).as_posix()
            if relative_key in referenced:
                continue
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if modified_at <= cutoff:
                orphaned_files.append(path)

        for orphan in orphaned_files:
            relative_key = orphan.relative_to(root).as_posix()
            action = "Would delete" if options["dry_run"] else "Deleted"
            self.stdout.write(f"{action} orphaned artifact: {relative_key}")
            if not options["dry_run"]:
                orphan.unlink(missing_ok=True)

        if not options["dry_run"]:
            for directory in sorted((path for path in root.rglob("*") if path.is_dir()), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {len(orphaned_files)} orphaned artifact(s) older than {options['older_than_hours']} hour(s)."
            )
        )

