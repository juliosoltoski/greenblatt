from unittest.mock import patch

from django.test import SimpleTestCase


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
