from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.jobs.models import JobRun
from apps.jobs.retries import RetryableJobError, error_code_for_exception, is_retryable_exception, next_retry_delay_seconds
from apps.jobs.tasks import run_smoke_job
from apps.workspaces.models import WorkspaceMembership


User = get_user_model()


class JobRetryHelperTests(TestCase):
    def test_retry_helpers_classify_errors_and_backoff(self) -> None:
        retryable = RetryableJobError("transient", error_code="provider_throttle")

        self.assertTrue(is_retryable_exception(retryable))
        self.assertEqual(error_code_for_exception(retryable), "provider_throttle")
        self.assertEqual(next_retry_delay_seconds(0), 5)
        self.assertEqual(next_retry_delay_seconds(2), 20)


class JobTaskLifecycleTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="operator", password="secret-pass-123")
        self.workspace = self.user.workspace_memberships.get().workspace

    @patch("apps.jobs.tasks.time.sleep", return_value=None)
    def test_smoke_task_marks_job_succeeded(self, _sleep) -> None:
        job = JobRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            job_type="smoke_test",
            metadata={"request": {"failure_mode": "success"}},
        )

        result = run_smoke_job.apply(
            kwargs={"job_run_id": job.id, "step_count": 3, "step_delay_ms": 0, "failure_mode": "success"},
            throw=False,
        )

        self.assertTrue(result.successful())
        job.refresh_from_db()
        self.assertEqual(job.state, JobRun.State.SUCCEEDED)
        self.assertEqual(job.progress_percent, 100)
        self.assertEqual(job.metadata["result"]["message"], "Smoke task completed successfully.")

    @patch("apps.jobs.tasks.time.sleep", return_value=None)
    def test_smoke_task_marks_job_failed(self, _sleep) -> None:
        job = JobRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            job_type="smoke_test",
            metadata={"request": {"failure_mode": "fail"}},
        )

        result = run_smoke_job.apply(
            kwargs={"job_run_id": job.id, "step_count": 2, "step_delay_ms": 0, "failure_mode": "fail"},
            throw=False,
        )

        self.assertFalse(result.successful())
        job.refresh_from_db()
        self.assertEqual(job.state, JobRun.State.FAILED)
        self.assertEqual(job.error_code, "runtime_error")
        self.assertIn("Synthetic smoke failure requested.", job.error_message)


class JobApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="analyst", password="secret-pass-123")
        self.client.force_login(self.user)
        self.workspace = self.user.workspace_memberships.get().workspace

    def test_job_list_requires_authentication(self) -> None:
        self.client.logout()

        response = self.client.get("/api/v1/jobs/")

        self.assertEqual(response.status_code, 403)

    @patch("apps.jobs.services.run_smoke_job.apply_async")
    def test_launch_smoke_job_returns_queued_job(self, apply_async) -> None:
        apply_async.return_value = SimpleNamespace(id="task-123")

        response = self.client.post(
            "/api/v1/jobs/smoke/",
            data={"workspace_id": self.workspace.id, "step_count": 3, "step_delay_ms": 10, "failure_mode": "success"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["state"], JobRun.State.QUEUED)
        self.assertEqual(payload["job_type"], "smoke_test")
        self.assertEqual(payload["celery_task_id"], "task-123")

        detail = self.client.get(f"/api/v1/jobs/{payload['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], payload["id"])

        listing = self.client.get(f"/api/v1/jobs/?workspace_id={self.workspace.id}")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()["results"]), 1)

    def test_viewer_cannot_launch_job(self) -> None:
        owner = User.objects.create_user(username="owner", password="secret-pass-123")
        viewer = User.objects.create_user(username="viewer", password="secret-pass-123")
        workspace = owner.workspace_memberships.get().workspace
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=viewer,
            role=WorkspaceMembership.Role.VIEWER,
        )
        self.client.force_login(viewer)

        response = self.client.post(
            "/api/v1/jobs/smoke/",
            data={"workspace_id": workspace.id, "step_count": 2, "step_delay_ms": 10, "failure_mode": "success"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
