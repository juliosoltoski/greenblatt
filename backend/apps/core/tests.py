import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from apps.core.data_quality import build_backtest_data_quality_payload, build_screen_data_quality_payload
from apps.core.provider_operations import ProviderCacheWarmJobService
from apps.jobs.models import JobRun
from apps.universes.models import UniverseUpload
from apps.universes.models import Universe, UniverseEntry
from greenblatt.models import SecuritySnapshot


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
        self.workspace = self.user.workspace_memberships.get().workspace
        self.universe = Universe.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Warmable universe",
            description="",
            source_type=Universe.SourceType.MANUAL,
            entry_count=2,
        )
        UniverseEntry.objects.bulk_create(
            [
                UniverseEntry(universe=self.universe, position=1, raw_ticker="AAPL", normalized_ticker="AAPL"),
                UniverseEntry(universe=self.universe, position=2, raw_ticker="MSFT", normalized_ticker="MSFT"),
            ]
        )

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

    def test_provider_diagnostics_endpoint_returns_failure_summary_and_workspace_usage(self) -> None:
        JobRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            job_type="screen_run",
            state=JobRun.State.FAILED,
            error_code="provider_failure",
            error_message="Yahoo rate limit exceeded for this request.",
            metadata={"provider_failure": {"provider_name": "yahoo", "workflow": "screen"}},
        )

        response = self.client.get(f"/api/v1/providers/diagnostics/?workspace_id={self.workspace.id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workspace_id"], self.workspace.id)
        self.assertEqual(payload["workspace_usage"]["resource_counts"]["universes"], 1)
        yahoo_entry = next(item for item in payload["providers"] if item["key"] == "yahoo")
        self.assertEqual(yahoo_entry["recent_failure_count"], 1)
        self.assertEqual(yahoo_entry["throttle_events"], 1)
        self.assertTrue(payload["recommendations"])

    @patch("apps.core.tasks.run_provider_cache_warm_job.apply_async")
    def test_provider_cache_warm_launch_returns_queued_job(self, apply_async) -> None:
        apply_async.return_value = SimpleNamespace(id="warm-task-123")

        response = self.client.post(
            "/api/v1/providers/cache-warm/",
            data={
                "workspace_id": self.workspace.id,
                "universe_id": self.universe.id,
                "sample_size": 2,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["job"]["job_type"], "provider_cache_warm")
        self.assertEqual(payload["job"]["celery_task_id"], "warm-task-123")

    def test_provider_cache_warm_service_executes_with_fake_provider(self) -> None:
        class FakeProvider:
            provider_name = "fake"
            supports_historical_fundamentals = False

            def get_snapshots(self, tickers, *, as_of=None, include_momentum=True):
                return [
                    SecuritySnapshot(ticker=ticker, company_name=ticker, market_cap=1_000_000_000, ebit=100_000_000, as_of=date(2025, 1, 1))
                    for ticker in tickers
                ]

        job = JobRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            job_type="provider_cache_warm",
            metadata={
                "request": {
                    "universe_id": self.universe.id,
                    "sample_size": 2,
                    "refresh_cache": False,
                    "cache_ttl_hours": 24.0,
                    "provider": {
                        "provider_name": "yahoo",
                        "fallback_provider_name": None,
                        "use_cache": True,
                        "refresh_cache": False,
                        "cache_ttl_hours": 24.0,
                    },
                }
            },
        )

        payload = ProviderCacheWarmJobService(provider_factory=lambda _config: FakeProvider()).execute_cache_warm_job(job_run_id=job.id, job=job)

        self.assertEqual(payload["job_type"], "provider_cache_warm")
        self.assertEqual(payload["requested_ticker_count"], 2)
        self.assertEqual(payload["warmed_ticker_count"], 2)
        self.assertEqual(payload["data_quality"]["warning_count"], 0)


class DataQualityHelperTests(SimpleTestCase):
    def test_screen_data_quality_flags_low_coverage_and_fallback(self) -> None:
        payload = build_screen_data_quality_payload(
            resolved_count=120,
            result_count=8,
            exclusion_count=80,
            top_n=30,
            fallback_used=True,
        )

        self.assertEqual(payload["severity"], "warning")
        self.assertGreaterEqual(payload["warning_count"], 3)

    def test_backtest_data_quality_flags_sparse_history(self) -> None:
        payload = build_backtest_data_quality_payload(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 1),
            equity_point_count=5,
            trade_count=0,
            review_target_count=0,
            final_holding_count=0,
            fallback_used=False,
        )

        self.assertEqual(payload["severity"], "warning")
        self.assertGreaterEqual(payload["warning_count"], 2)
