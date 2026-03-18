from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.workspaces.models import WorkspaceMembership
from apps.workspaces.permissions import get_workspace_membership, has_workspace_role


User = get_user_model()


class WorkspaceModelTests(TestCase):
    def test_creating_user_creates_default_workspace_and_owner_membership(self) -> None:
        user = User.objects.create_user(username="owner", password="secret-pass-123", first_name="Pat", last_name="Lee")

        memberships = list(user.workspace_memberships.select_related("workspace"))

        self.assertEqual(len(memberships), 1)
        membership = memberships[0]
        self.assertEqual(membership.role, WorkspaceMembership.Role.OWNER)
        self.assertEqual(membership.workspace.owner, user)
        self.assertEqual(membership.workspace.name, "Pat Lee Workspace")

    def test_role_helpers_respect_workspace_membership_hierarchy(self) -> None:
        owner = User.objects.create_user(username="owner", password="secret-pass-123")
        viewer = User.objects.create_user(username="viewer", password="secret-pass-123")
        owner_workspace = owner.workspace_memberships.get().workspace
        WorkspaceMembership.objects.create(
            workspace=owner_workspace,
            user=viewer,
            role=WorkspaceMembership.Role.VIEWER,
        )

        self.assertEqual(get_workspace_membership(viewer, owner_workspace).role, WorkspaceMembership.Role.VIEWER)
        self.assertTrue(has_workspace_role(owner, owner_workspace, WorkspaceMembership.Role.ADMIN))
        self.assertFalse(has_workspace_role(viewer, owner_workspace, WorkspaceMembership.Role.ANALYST))


class WorkspaceApiTests(TestCase):
    def test_workspace_list_requires_authentication(self) -> None:
        response = self.client.get("/api/v1/workspaces/")

        self.assertEqual(response.status_code, 403)

    def test_workspace_list_returns_membership_context(self) -> None:
        user = User.objects.create_user(username="analyst", password="secret-pass-123")
        self.client.force_login(user)

        response = self.client.get("/api/v1/workspaces/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["role"], WorkspaceMembership.Role.OWNER)
