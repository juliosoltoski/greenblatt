from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.jobs.models import JobRun
from apps.jobs.services import JobService
from apps.screens.models import ScreenExclusion, ScreenResultRow, ScreenRun
from apps.screens.services import ScreenLaunchRequest, ScreenRunService
from apps.screens.tasks import run_screen_job
from apps.universes.models import Universe
from apps.universes.services import ArtifactStorage
from apps.workspaces.models import WorkspaceMembership
from greenblatt.models import SecuritySnapshot
from greenblatt.providers.base import MarketDataProvider


User = get_user_model()


class FakeProvider(MarketDataProvider):
    provider_name = "fake"
    supports_historical_fundamentals = False

    def __init__(self, snapshots: list[SecuritySnapshot]) -> None:
        self.snapshots = snapshots

    def get_snapshots(self, tickers, *, as_of=None, include_momentum=True):
        lookup = {snapshot.ticker: snapshot for snapshot in self.snapshots}
        return [replace(lookup[ticker]) for ticker in tickers if ticker in lookup]

    def get_price_history(self, tickers, *, start, end, interval="1d", auto_adjust=False):
        raise NotImplementedError

    def get_us_equity_candidates(self, *, limit: int = 3_000):
        return [snapshot.ticker for snapshot in self.snapshots][:limit]


def make_snapshot(
    ticker: str,
    rank_seed: int = 0,
    *,
    sector: str = "Technology",
    industry: str = "Software",
    is_adr: bool = False,
    momentum_6m: float | None = None,
) -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker=ticker,
        company_name=f"{ticker} Holdings",
        sector=sector,
        industry=industry,
        is_adr=is_adr,
        market_cap=220 - rank_seed,
        ebit=50 - rank_seed,
        current_assets=60,
        current_liabilities=20,
        cash_and_equivalents=10,
        total_debt=20,
        net_pp_e=60,
        momentum_6m=momentum_6m,
    )


class ScreenTaskLifecycleTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="screener", password="secret-pass-123")
        self.workspace = self.user.workspace_memberships.get().workspace
        self.universe = Universe.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Saved Universe",
            source_type=Universe.SourceType.MANUAL,
            entry_count=3,
        )
        self.universe.entries.create(position=1, raw_ticker="AAA", normalized_ticker="AAA")
        self.universe.entries.create(position=2, raw_ticker="BBB", normalized_ticker="BBB")
        self.universe.entries.create(position=3, raw_ticker="ADR", normalized_ticker="ADR")

    def test_screen_task_persists_rows_exclusions_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(ARTIFACT_STORAGE_ROOT=temp_dir):
                job = JobService().create_job(
                    workspace=self.workspace,
                    created_by=self.user,
                    job_type="screen_run",
                    metadata={"request": {"universe_id": self.universe.id}},
                    current_step="Queued for screening",
                )
                screen_run = ScreenRun.objects.create(
                    workspace=self.workspace,
                    created_by=self.user,
                    universe=self.universe,
                    job=job,
                    top_n=5,
                    momentum_mode="overlay",
                )

                fake_provider = FakeProvider(
                    [
                        make_snapshot("AAA", rank_seed=1, momentum_6m=0.10),
                        make_snapshot("BBB", rank_seed=2, momentum_6m=0.25),
                        make_snapshot("ADR", rank_seed=3, is_adr=True),
                    ]
                )

                with patch("apps.screens.services.build_provider", return_value=fake_provider):
                    result = run_screen_job.apply(
                        kwargs={"job_run_id": job.id, "screen_run_id": screen_run.id},
                        throw=False,
                    )

                self.assertTrue(result.successful())
                job.refresh_from_db()
                screen_run.refresh_from_db()

                self.assertEqual(job.state, JobRun.State.SUCCEEDED)
                self.assertEqual(screen_run.result_count, 2)
                self.assertEqual(screen_run.exclusion_count, 1)
                self.assertEqual(screen_run.summary["top_tickers"], ["AAA", "BBB"])
                self.assertEqual(screen_run.summary["provider"]["resolved_provider_name"], "fake")
                self.assertTrue(screen_run.has_export)
                self.assertTrue(Path(temp_dir, screen_run.export_storage_key).exists())

                rows = list(ScreenResultRow.objects.filter(screen_run=screen_run))
                self.assertEqual([row.ticker for row in rows], ["AAA", "BBB"])
                self.assertEqual(rows[0].position, 1)
                self.assertGreater(rows[0].final_score, 0)

                exclusions = list(ScreenExclusion.objects.filter(screen_run=screen_run))
                self.assertEqual(exclusions[0].ticker, "ADR")
                self.assertEqual(exclusions[0].reason, "adr excluded")

    def test_screen_task_marks_provider_build_failures_explicitly(self) -> None:
        job = JobService().create_job(
            workspace=self.workspace,
            created_by=self.user,
            job_type="screen_run",
            metadata={"request": {"universe_id": self.universe.id}},
            current_step="Queued for screening",
        )
        screen_run = ScreenRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            universe=self.universe,
            job=job,
            top_n=5,
            momentum_mode="overlay",
        )

        with patch("apps.screens.services.build_provider", side_effect=RuntimeError("Yahoo bootstrap failed")):
            result = run_screen_job.apply(
                kwargs={"job_run_id": job.id, "screen_run_id": screen_run.id},
                throw=False,
            )

        self.assertFalse(result.successful())
        job.refresh_from_db()
        self.assertEqual(job.state, JobRun.State.FAILED)
        self.assertEqual(job.error_code, "provider_build_failed")
        self.assertEqual(job.metadata["provider_failure"]["provider_name"], "yahoo")
        self.assertEqual(job.metadata["provider_failure"]["workflow"], "screen")


class ScreenApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="analyst", password="secret-pass-123")
        self.client.force_login(self.user)
        self.workspace = self.user.workspace_memberships.get().workspace
        self.universe = Universe.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Web Universe",
            source_type=Universe.SourceType.MANUAL,
            entry_count=2,
        )
        self.universe.entries.create(position=1, raw_ticker="AAA", normalized_ticker="AAA")
        self.universe.entries.create(position=2, raw_ticker="BBB", normalized_ticker="BBB")

    @patch("apps.screens.tasks.run_screen_job.apply_async")
    def test_launch_list_and_detail_screen_run(self, apply_async) -> None:
        apply_async.return_value = SimpleNamespace(id="screen-task-123")

        response = self.client.post(
            "/api/v1/screens/",
            data={
                "workspace_id": self.workspace.id,
                "universe_id": self.universe.id,
                "top_n": 25,
                "momentum_mode": "overlay",
                "sector_allowlist": ["Technology"],
                "min_market_cap": 1_000_000_000,
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["job"]["state"], JobRun.State.QUEUED)
        self.assertEqual(payload["job"]["celery_task_id"], "screen-task-123")
        self.assertEqual(payload["universe"]["id"], self.universe.id)

        listing = self.client.get(f"/api/v1/screens/?workspace_id={self.workspace.id}")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)
        self.assertEqual(len(listing.json()["results"]), 1)

        detail = self.client.get(f"/api/v1/screens/{payload['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], payload["id"])

    def test_results_exclusions_and_export_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(ARTIFACT_STORAGE_ROOT=temp_dir):
                job = JobRun.objects.create(
                    workspace=self.workspace,
                    created_by=self.user,
                    job_type="screen_run",
                    state=JobRun.State.SUCCEEDED,
                    progress_percent=100,
                    current_step="Completed",
                )
                screen_run = ScreenRun.objects.create(
                    workspace=self.workspace,
                    created_by=self.user,
                    universe=self.universe,
                    job=job,
                    top_n=30,
                    result_count=2,
                    exclusion_count=1,
                )
                ScreenResultRow.objects.create(
                    screen_run=screen_run,
                    position=1,
                    ticker="AAA",
                    company_name="AAA Holdings",
                    final_score=2,
                    return_on_capital=0.45,
                    earnings_yield=0.21,
                )
                ScreenResultRow.objects.create(
                    screen_run=screen_run,
                    position=2,
                    ticker="BBB",
                    company_name="BBB Holdings",
                    final_score=4,
                    return_on_capital=0.40,
                    earnings_yield=0.18,
                )
                ScreenExclusion.objects.create(screen_run=screen_run, ticker="ADR", reason="adr excluded")
                stored = ArtifactStorage(root=temp_dir).store_artifact(
                    workspace=self.workspace,
                    category="screens",
                    original_filename="screen-results.csv",
                    content=b"ticker,final_score\nAAA,2\nBBB,4\n",
                )
                screen_run.export_storage_backend = stored.storage_backend
                screen_run.export_storage_key = stored.storage_key
                screen_run.export_filename = "screen-results.csv"
                screen_run.export_checksum_sha256 = stored.checksum_sha256
                screen_run.export_size_bytes = stored.size_bytes
                screen_run.save()

                rows = self.client.get(f"/api/v1/screens/{screen_run.id}/results/?sort=final_score&direction=desc&page_size=1")
                self.assertEqual(rows.status_code, 200)
                row_payload = rows.json()
                self.assertEqual(row_payload["count"], 2)
                self.assertEqual(len(row_payload["results"]), 1)
                self.assertEqual(row_payload["results"][0]["ticker"], "BBB")

                exclusions = self.client.get(f"/api/v1/screens/{screen_run.id}/exclusions/")
                self.assertEqual(exclusions.status_code, 200)
                self.assertEqual(exclusions.json()["results"][0]["ticker"], "ADR")

                export_response = self.client.get(f"/api/v1/screens/{screen_run.id}/export/")
                self.assertEqual(export_response.status_code, 200)
                self.assertEqual(export_response.headers["Content-Disposition"], 'attachment; filename="screen-results.csv"')

                export_json = self.client.get(f"/api/v1/screens/{screen_run.id}/export/json/")
                self.assertEqual(export_json.status_code, 200)
                self.assertEqual(export_json.json()["run"]["workflow_kind"], "screen")
                self.assertEqual(len(export_json.json()["results"]), 2)

    def test_viewer_cannot_launch_screen(self) -> None:
        owner = User.objects.create_user(username="owner", password="secret-pass-123")
        viewer = User.objects.create_user(username="viewer", password="secret-pass-123")
        workspace = owner.workspace_memberships.get().workspace
        universe = Universe.objects.create(
            workspace=workspace,
            created_by=owner,
            name="Owner Universe",
            source_type=Universe.SourceType.MANUAL,
            entry_count=1,
        )
        universe.entries.create(position=1, raw_ticker="AAA", normalized_ticker="AAA")
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=viewer,
            role=WorkspaceMembership.Role.VIEWER,
        )
        self.client.force_login(viewer)

        response = self.client.post(
            "/api/v1/screens/",
            data={"workspace_id": workspace.id, "universe_id": universe.id},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(WORKSPACE_MAX_CONCURRENT_RESEARCH_JOBS=1)
    def test_research_concurrency_limit_rejects_additional_screen_launches(self) -> None:
        JobRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            job_type="backtest_run",
            state=JobRun.State.RUNNING,
            progress_percent=50,
            current_step="Running",
        )

        response = self.client.post(
            "/api/v1/screens/",
            data={
                "workspace_id": self.workspace.id,
                "universe_id": self.universe.id,
                "top_n": 25,
                "momentum_mode": "overlay",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 429)
        self.assertIn("Workspace research concurrency limit reached", response.json()["detail"])
