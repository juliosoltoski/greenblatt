from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from apps.jobs.models import JobRun
from apps.workspaces.models import WorkspaceMembership


User = get_user_model()


class AuthApiTests(TestCase):
    def test_get_csrf_sets_cookie(self) -> None:
        client = Client(enforce_csrf_checks=True)

        response = client.get("/api/v1/auth/csrf/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    def test_login_me_and_logout_flow(self) -> None:
        user = User.objects.create_user(
            username="analyst",
            email="analyst@example.com",
            password="secret-pass-123",
            first_name="Ada",
            last_name="Lovelace",
        )

        client = Client(enforce_csrf_checks=True)
        csrf_response = client.get("/api/v1/auth/csrf/")
        csrf_token = csrf_response.cookies["csrftoken"].value

        login_response = client.post(
            "/api/v1/auth/login/",
            data={"username": "analyst", "password": "secret-pass-123"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(login_response.status_code, 200)
        payload = login_response.json()
        self.assertEqual(payload["username"], "analyst")
        self.assertEqual(payload["display_name"], "Ada Lovelace")
        self.assertEqual(payload["active_workspace"]["role"], WorkspaceMembership.Role.OWNER)

        me_response = client.get("/api/v1/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        me_payload = me_response.json()
        self.assertEqual(me_payload["email"], "analyst@example.com")
        self.assertEqual(len(me_payload["workspaces"]), 1)
        self.assertEqual(me_payload["workspaces"][0]["owner_id"], user.id)

        logout_csrf = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value
        logout_response = client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=logout_csrf)
        self.assertEqual(logout_response.status_code, 200)

        post_logout_response = client.get("/api/v1/auth/me/")
        self.assertEqual(post_logout_response.status_code, 403)

    def test_login_rejects_invalid_credentials(self) -> None:
        User.objects.create_user(username="analyst", password="secret-pass-123")
        client = Client(enforce_csrf_checks=True)
        csrf_token = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value

        response = client.post(
            "/api/v1/auth/login/",
            data={"username": "analyst", "password": "wrong-password"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid username or password.")

    def test_patch_current_user_updates_profile_fields(self) -> None:
        user = User.objects.create_user(username="analyst", password="secret-pass-123", first_name="Ada", last_name="Lovelace")
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        csrf_token = client.get("/api/v1/auth/csrf/").cookies["csrftoken"].value

        response = client.patch(
            "/api/v1/auth/me/",
            data={"first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Grace")
        self.assertEqual(user.last_name, "Hopper")
        self.assertEqual(user.email, "grace@example.com")

    def test_account_settings_returns_plan_usage_and_notices(self) -> None:
        user = User.objects.create_user(username="analyst", password="secret-pass-123")
        client = Client()
        client.force_login(user)
        workspace = user.workspace_memberships.get().workspace
        JobRun.objects.create(
            workspace=workspace,
            created_by=user,
            job_type="screen_run",
            state=JobRun.State.RUNNING,
        )

        response = client.get(f"/api/v1/auth/settings/?workspace_id={workspace.id}")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["username"], "analyst")
        self.assertEqual(payload["plan"]["workspace_plan_type"], "personal")
        self.assertEqual(payload["workspace"]["active_jobs"]["total"], 1)
        self.assertIn("research_only", payload["notices"])
        self.assertIsNone(payload["support_overview"])

    def test_account_settings_includes_support_overview_for_staff(self) -> None:
        staff = User.objects.create_user(username="staff", password="secret-pass-123", is_staff=True)
        client = Client()
        client.force_login(staff)
        workspace = staff.workspace_memberships.get().workspace
        JobRun.objects.create(
            workspace=workspace,
            created_by=staff,
            job_type="backtest_run",
            state=JobRun.State.FAILED,
            error_code="provider_failure",
            error_message="Provider failure",
            updated_at=timezone.now(),
        )

        response = client.get("/api/v1/auth/settings/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNotNone(payload["support_overview"])
        self.assertGreaterEqual(payload["support_overview"]["workspace_count"], 1)
