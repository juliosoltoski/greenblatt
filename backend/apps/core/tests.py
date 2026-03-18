import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.universes.models import UniverseUpload


class HealthEndpointTests(SimpleTestCase):
    def test_live_health_returns_ok(self) -> None:
        response = self.client.get("/health/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(response.headers["X-Request-ID"])

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

    @patch("apps.core.views.metrics_content", return_value=b"# HELP greenblatt_test_metric test\n")
    def test_metrics_endpoint_returns_prometheus_payload(self, _metrics_content) -> None:
        response = self.client.get("/metrics/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["Content-Type"])
        self.assertIn("greenblatt_test_metric", response.content.decode("utf-8"))

    @patch("apps.core.views.metrics_content", return_value=b"# HELP greenblatt_test_metric test\n")
    @override_settings(METRICS_AUTH_TOKEN="metrics-secret")
    def test_metrics_endpoint_requires_auth_token_when_configured(self, _metrics_content) -> None:
        forbidden = self.client.get("/metrics/")
        allowed = self.client.get("/metrics/", HTTP_X_METRICS_TOKEN="metrics-secret")

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(allowed.status_code, 200)


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


class ProviderApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="provider-admin", password="secret-pass-123")
        self.client.force_login(self.user)

    @patch(
        "apps.core.views.configured_provider_health_payload",
        return_value={
            "default_provider": "yahoo",
            "fallback_provider": "alpha_vantage",
            "providers": [
                {"key": "yahoo", "state": "ok"},
                {"key": "alpha_vantage", "state": "unconfigured"},
            ],
        },
    )
    def test_provider_endpoint_returns_configured_health_payload(self, configured_provider_health_payload_mock) -> None:
        response = self.client.get("/api/v1/providers/?probe=true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["default_provider"], "yahoo")
        configured_provider_health_payload_mock.assert_called_once_with(probe=True)
