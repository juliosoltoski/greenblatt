from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

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
