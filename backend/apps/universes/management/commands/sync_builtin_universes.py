from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.universes.builtin_sync import sync_builtin_universes
from apps.workspaces.models import Workspace


class Command(BaseCommand):
    help = "Create or refresh system-managed built-in universes for one workspace or all workspaces."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--workspace-id", type=int, help="Limit the sync to a single workspace.")
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail the command when any built-in profile cannot be refreshed.",
        )

    def handle(self, *args, **options) -> None:
        workspace = None
        workspace_id = options.get("workspace_id")
        if workspace_id is not None:
            workspace = Workspace.objects.select_related("owner").filter(pk=workspace_id).first()
            if workspace is None:
                raise CommandError(f"Workspace {workspace_id} does not exist.")

        result = sync_builtin_universes(workspace=workspace)
        for error in result.errors:
            self.stderr.write(self.style.WARNING(error))

        summary = (
            "Built-in universe sync completed: "
            f"created={result.created} updated={result.updated} errors={len(result.errors)}"
        )
        if result.errors and options["strict"]:
            raise CommandError(summary)
        self.stdout.write(self.style.SUCCESS(summary))
