from __future__ import annotations

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.universes.models import Universe, UniverseUpload
from apps.universes.services import UniverseInputError, parse_ticker_text
from apps.workspaces.models import WorkspaceMembership


User = get_user_model()


class UniverseParsingTests(TestCase):
    def test_parse_ticker_text_normalizes_and_deduplicates(self) -> None:
        entries = parse_ticker_text("ticker\nbrk.b\n msft \nBRK-B\n0700.hk\n")

        self.assertEqual(
            [entry.normalized_ticker for entry in entries],
            ["BRK-B", "MSFT", "0700.HK"],
        )

    def test_parse_ticker_text_reports_invalid_lines(self) -> None:
        with self.assertRaises(UniverseInputError) as exc:
            parse_ticker_text("MSFT\nbad/ticker\n")

        self.assertEqual(exc.exception.detail, "Universe input contains invalid tickers.")
        self.assertIn("Line 2", exc.exception.errors[0])


class UniverseApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="analyst", password="secret-pass-123")
        self.client.force_login(self.user)
        self.workspace = self.user.workspace_memberships.get().workspace

    def test_profile_list_returns_existing_definitions(self) -> None:
        response = self.client.get("/api/v1/universe-profiles/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item["key"] == "sector_tech" for item in payload["results"]))
        dynamic_profile = next(item for item in payload["results"] if item["key"] == "us_top_3000")
        self.assertEqual(dynamic_profile["estimated_entry_count"], 3000)

    def test_create_manual_universe_and_fetch_detail_preview(self) -> None:
        response = self.client.post(
            "/api/v1/universes/",
            data={
                "name": "Manual Watchlist",
                "description": "Core idea basket",
                "source_type": "manual",
                "manual_tickers": "MSFT\nAAPL\nbrk.b\n",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["entry_count"], 3)
        self.assertEqual(payload["entries"][2]["normalized_ticker"], "BRK-B")

        detail = self.client.get(f"/api/v1/universes/{payload['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["entries"]), 3)

    def test_create_built_in_universe_from_packaged_profile(self) -> None:
        response = self.client.post(
            "/api/v1/universes/",
            data={
                "name": "Tech Profile",
                "source_type": "built_in",
                "profile_key": "sector_tech",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["profile_key"], "sector_tech")
        self.assertGreater(payload["entry_count"], 0)

    def test_uploaded_universe_persists_source_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(ARTIFACT_STORAGE_ROOT=temp_dir):
                response = self.client.post(
                    "/api/v1/universes/",
                    data={
                        "name": "Uploaded Universe",
                        "source_type": "uploaded_file",
                        "upload_file": SimpleUploadedFile(
                            "tickers.txt",
                            b"MSFT\nAAPL\nNVDA\n",
                            content_type="text/plain",
                        ),
                    },
                )

                self.assertEqual(response.status_code, 201)
                payload = response.json()
                self.assertEqual(payload["entry_count"], 3)
                self.assertIsNotNone(payload["source_upload"])
                upload = UniverseUpload.objects.get(pk=payload["source_upload"]["id"])
                self.assertTrue(Path(temp_dir, upload.storage_key).exists())

    def test_invalid_upload_returns_clear_validation_errors(self) -> None:
        response = self.client.post(
            "/api/v1/universes/",
            data={
                "name": "Bad Upload",
                "source_type": "uploaded_file",
                "upload_file": SimpleUploadedFile(
                    "tickers.txt",
                    b"MSFT\nBAD/TICKER\n",
                    content_type="text/plain",
                ),
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["detail"], "Universe input contains invalid tickers.")
        self.assertIn("Line 2", payload["errors"][0])

    def test_patch_and_delete_universe(self) -> None:
        universe = Universe.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Original Name",
            source_type="manual",
            entry_count=1,
        )
        universe.entries.create(position=1, raw_ticker="MSFT", normalized_ticker="MSFT")

        patch_response = self.client.patch(
            f"/api/v1/universes/{universe.id}/",
            data={
                "name": "Renamed Universe",
                "description": "Updated",
                "is_starred": True,
                "tags": ["favorite", "review"],
                "notes": "First pass notes",
            },
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["name"], "Renamed Universe")
        self.assertTrue(patch_response.json()["is_starred"])
        self.assertEqual(patch_response.json()["tags"], ["favorite", "review"])
        self.assertEqual(patch_response.json()["notes"], "First pass notes")

        listing = self.client.get("/api/v1/universes/?starred_only=true")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["results"][0]["id"], universe.id)

        delete_response = self.client.delete(f"/api/v1/universes/{universe.id}/")
        self.assertEqual(delete_response.status_code, 204)
        self.assertFalse(Universe.objects.filter(pk=universe.id).exists())

    def test_viewer_cannot_create_universe(self) -> None:
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
            "/api/v1/universes/",
            data={
                "workspace_id": workspace.id,
                "name": "Viewer Universe",
                "source_type": "manual",
                "manual_tickers": "MSFT",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
