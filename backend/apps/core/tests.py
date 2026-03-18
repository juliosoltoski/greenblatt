import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test import SimpleTestCase

from apps.universes.models import UniverseUpload


class HealthEndpointTests(SimpleTestCase):
    def test_live_health_returns_ok(self) -> None:
        response = self.client.get("/health/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("apps.core.views._database_health", return_value={"ok": True, "service": "database"})
    @patch("apps.core.views._redis_health", return_value={"ok": True, "service": "redis"})
    def test_ready_health_returns_ok_when_dependencies_are_ready(self, *_mocks) -> None:
        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("apps.core.views._database_health", return_value={"ok": False, "service": "database", "detail": "down"})
    @patch("apps.core.views._redis_health", return_value={"ok": True, "service": "redis"})
    def test_ready_health_returns_503_when_dependency_is_down(self, *_mocks) -> None:
        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "degraded")


User = get_user_model()


class CleanupArtifactsCommandTests(TestCase):
    def test_cleanup_artifacts_removes_only_orphans(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            user = User.objects.create_user(username="artifact-owner", password="secret-pass-123")
            workspace = user.workspace_memberships.get().workspace

            referenced_dir = Path(temp_dir, "workspaces", str(workspace.id))
            referenced_dir.mkdir(parents=True, exist_ok=True)
            referenced_path = referenced_dir / "referenced.csv"
            referenced_path.write_text("keep")
            UniverseUpload.objects.create(
                workspace=workspace,
                created_by=user,
                original_filename="referenced.csv",
                storage_key=referenced_path.relative_to(temp_dir).as_posix(),
                checksum_sha256="0" * 64,
                size_bytes=4,
            )

            orphan_path = referenced_dir / "orphan.csv"
            orphan_path.write_text("delete")

            with self.settings(
                ARTIFACT_STORAGE_BACKEND="filesystem",
                ARTIFACT_STORAGE_ROOT=temp_dir,
                ARTIFACT_ORPHAN_RETENTION_HOURS=0,
            ):
                call_command("cleanup_artifacts", "--older-than-hours", "0")

            self.assertTrue(referenced_path.exists())
            self.assertFalse(orphan_path.exists())
