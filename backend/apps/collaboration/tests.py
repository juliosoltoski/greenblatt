from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.strategy_templates.models import StrategyTemplate
from apps.universes.models import Universe


User = get_user_model()


class CollaborationApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="collab-owner",
            email="owner@example.com",
            password="secret-pass-123",
        )
        self.client.force_login(self.user)
        self.workspace = self.user.workspace_memberships.get().workspace
        self.universe = Universe.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Collaboration Universe",
            source_type=Universe.SourceType.MANUAL,
            entry_count=2,
        )
        self.universe.entries.create(position=1, raw_ticker="AAA", normalized_ticker="AAA")
        self.universe.entries.create(position=2, raw_ticker="BBB", normalized_ticker="BBB")
        self.template = StrategyTemplate.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Shared template",
            workflow_kind=StrategyTemplate.WorkflowKind.SCREEN,
            universe=self.universe,
            config={
                "top_n": 20,
                "momentum_mode": "none",
                "sector_allowlist": [],
                "min_market_cap": None,
                "exclude_financials": True,
                "exclude_utilities": True,
                "exclude_adrs": True,
                "use_cache": True,
                "refresh_cache": False,
                "cache_ttl_hours": 24.0,
            },
        )

    def test_comments_and_share_links_work_for_templates(self) -> None:
        created_comment = self.client.post(
            "/api/v1/collaboration/comments/",
            data={
                "resource_kind": "strategy_template",
                "resource_id": self.template.id,
                "body": "Start with the large-cap version first.",
            },
            content_type="application/json",
        )
        self.assertEqual(created_comment.status_code, 201)
        self.assertEqual(created_comment.json()["resource_kind"], "strategy_template")

        listed_comments = self.client.get(
            f"/api/v1/collaboration/comments/?workspace_id={self.workspace.id}&resource_kind=strategy_template&resource_id={self.template.id}"
        )
        self.assertEqual(listed_comments.status_code, 200)
        self.assertEqual(listed_comments.json()["count"], 1)

        created_share_link = self.client.post(
            "/api/v1/collaboration/share-links/",
            data={
                "resource_kind": "strategy_template",
                "resource_id": self.template.id,
                "label": "Team review",
                "access_scope": "token",
            },
            content_type="application/json",
        )
        self.assertEqual(created_share_link.status_code, 201)
        token = created_share_link.json()["token"]

        public_client = Client()
        shared = public_client.get(f"/api/v1/shared/{token}/")
        self.assertEqual(shared.status_code, 200)
        self.assertEqual(shared.json()["shared_resource"]["resource_kind"], "strategy_template")
        self.assertEqual(shared.json()["shared_resource"]["payload"]["id"], self.template.id)

    def test_collections_and_activity_feed_capture_workspace_actions(self) -> None:
        created_collection = self.client.post(
            "/api/v1/collaboration/collections/",
            data={
                "workspace_id": self.workspace.id,
                "name": "Quarterly review",
                "description": "Templates to revisit this quarter.",
                "is_pinned": True,
            },
            content_type="application/json",
        )
        self.assertEqual(created_collection.status_code, 201)
        collection_id = created_collection.json()["id"]

        added_item = self.client.post(
            f"/api/v1/collaboration/collections/{collection_id}/items/",
            data={
                "resource_kind": "strategy_template",
                "resource_id": self.template.id,
                "note": "First template to review.",
            },
            content_type="application/json",
        )
        self.assertEqual(added_item.status_code, 201)
        self.assertEqual(len(added_item.json()["items"]), 1)

        listed_collections = self.client.get(f"/api/v1/collaboration/collections/?workspace_id={self.workspace.id}")
        self.assertEqual(listed_collections.status_code, 200)
        self.assertEqual(listed_collections.json()["count"], 1)
        self.assertEqual(listed_collections.json()["results"][0]["items"][0]["resource"]["title"], self.template.name)

        activity = self.client.get(f"/api/v1/collaboration/activity-events/?workspace_id={self.workspace.id}")
        self.assertEqual(activity.status_code, 200)
        verbs = {item["verb"] for item in activity.json()["results"]}
        self.assertIn("collection_created", verbs)
        self.assertIn("collection_item_added", verbs)
