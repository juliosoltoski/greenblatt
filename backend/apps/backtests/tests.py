from __future__ import annotations

import tempfile
import zipfile
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.backtests.models import (
    BacktestEquityPoint,
    BacktestFinalHolding,
    BacktestReviewTarget,
    BacktestRun,
    BacktestTrade,
)
from apps.backtests.tasks import run_backtest_job
from apps.jobs.models import JobRun
from apps.jobs.services import JobService
from apps.universes.models import Universe
from apps.universes.services import ArtifactStorage
from apps.workspaces.models import WorkspaceMembership
from greenblatt.models import SecuritySnapshot
from greenblatt.providers.base import MarketDataProvider


User = get_user_model()


class FakeProvider(MarketDataProvider):
    provider_name = "fake"
    supports_historical_fundamentals = False

    def __init__(self, snapshots: list[SecuritySnapshot], prices: pd.DataFrame) -> None:
        self.snapshots = snapshots
        self.prices = prices

    def get_snapshots(self, tickers, *, as_of=None, include_momentum=True):
        lookup = {snapshot.ticker: snapshot for snapshot in self.snapshots}
        return [replace(lookup[ticker]) for ticker in tickers if ticker in lookup]

    def get_price_history(self, tickers, *, start, end, interval="1d", auto_adjust=False):
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)
        columns = [ticker for ticker in tickers if ticker in self.prices.columns]
        frame = self.prices.loc[(self.prices.index >= start) & (self.prices.index <= end), columns]
        return frame.copy()

    def get_us_equity_candidates(self, *, limit: int = 3_000):
        return [snapshot.ticker for snapshot in self.snapshots][:limit]


def make_snapshot(ticker: str, rank_seed: int) -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker=ticker,
        company_name=ticker,
        sector="Technology",
        industry="Software",
        market_cap=200 - rank_seed,
        ebit=60 - rank_seed,
        current_assets=80,
        current_liabilities=20,
        cash_and_equivalents=10,
        total_debt=20,
        net_pp_e=60,
    )


def make_prices() -> pd.DataFrame:
    dates = pd.date_range("2024-01-05", "2025-02-14", freq="W-FRI")
    return pd.DataFrame(
        {
            "AAA": [100.0] * 51 + [90.0] * (len(dates) - 51),
            "BBB": [100.0] * 53 + [120.0] * (len(dates) - 53),
            "CCC": [100.0] * len(dates),
            "^GSPC": [100.0 + idx for idx, _ in enumerate(dates)],
        },
        index=dates,
    )


class BacktestTaskLifecycleTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="backtester", password="secret-pass-123")
        self.workspace = self.user.workspace_memberships.get().workspace
        self.universe = Universe.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Backtest Universe",
            source_type=Universe.SourceType.MANUAL,
            entry_count=3,
        )
        self.universe.entries.create(position=1, raw_ticker="AAA", normalized_ticker="AAA")
        self.universe.entries.create(position=2, raw_ticker="BBB", normalized_ticker="BBB")
        self.universe.entries.create(position=3, raw_ticker="CCC", normalized_ticker="CCC")

    def test_backtest_task_persists_curve_trades_holdings_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(ARTIFACT_STORAGE_ROOT=temp_dir):
                job = JobService().create_job(
                    workspace=self.workspace,
                    created_by=self.user,
                    job_type="backtest_run",
                    metadata={"request": {"universe_id": self.universe.id}},
                    current_step="Queued for backtesting",
                )
                backtest_run = BacktestRun.objects.create(
                    workspace=self.workspace,
                    created_by=self.user,
                    universe=self.universe,
                    job=job,
                    start_date=date(2024, 1, 5),
                    end_date=date(2025, 2, 14),
                    initial_capital=100000,
                    portfolio_size=2,
                    benchmark="^GSPC",
                )

                fake_provider = FakeProvider(
                    snapshots=[make_snapshot("AAA", 1), make_snapshot("BBB", 2), make_snapshot("CCC", 3)],
                    prices=make_prices(),
                )

                with patch("apps.backtests.services.build_provider", return_value=fake_provider):
                    result = run_backtest_job.apply(
                        kwargs={"job_run_id": job.id, "backtest_run_id": backtest_run.id},
                        throw=False,
                    )

                self.assertTrue(result.successful())
                job.refresh_from_db()
                backtest_run.refresh_from_db()

                self.assertEqual(job.state, JobRun.State.SUCCEEDED)
                self.assertGreater(backtest_run.equity_point_count, 0)
                self.assertEqual(backtest_run.trade_count, 6)
                self.assertEqual(backtest_run.final_holding_count, 2)
                self.assertEqual(backtest_run.summary["provider"]["resolved_provider_name"], "fake")
                self.assertTrue(backtest_run.has_export)
                self.assertIn("total_return", backtest_run.summary)
                self.assertTrue(Path(temp_dir, backtest_run.export_storage_key).exists())

                self.assertGreater(BacktestEquityPoint.objects.filter(backtest_run=backtest_run).count(), 0)
                self.assertEqual(BacktestTrade.objects.filter(backtest_run=backtest_run).count(), 6)
                self.assertGreater(BacktestReviewTarget.objects.filter(backtest_run=backtest_run).count(), 0)
                self.assertEqual(BacktestFinalHolding.objects.filter(backtest_run=backtest_run).count(), 2)

                with zipfile.ZipFile(Path(temp_dir, backtest_run.export_storage_key)) as archive:
                    names = set(archive.namelist())
                    self.assertIn("summary.json", names)
                    self.assertIn("equity_curve.csv", names)
                    self.assertIn("trades.csv", names)
                    self.assertIn("final_holdings.csv", names)

    def test_backtest_task_marks_provider_build_failures_explicitly(self) -> None:
        job = JobService().create_job(
            workspace=self.workspace,
            created_by=self.user,
            job_type="backtest_run",
            metadata={"request": {"universe_id": self.universe.id}},
            current_step="Queued for backtesting",
        )
        backtest_run = BacktestRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            universe=self.universe,
            job=job,
            start_date=date(2024, 1, 5),
            end_date=date(2025, 2, 14),
            initial_capital=100000,
            portfolio_size=2,
            benchmark="^GSPC",
        )

        with patch("apps.backtests.services.build_provider", side_effect=RuntimeError("Yahoo bootstrap failed")):
            result = run_backtest_job.apply(
                kwargs={"job_run_id": job.id, "backtest_run_id": backtest_run.id},
                throw=False,
            )

        self.assertFalse(result.successful())
        job.refresh_from_db()
        self.assertEqual(job.state, JobRun.State.FAILED)
        self.assertEqual(job.error_code, "provider_build_failed")
        self.assertEqual(job.metadata["provider_failure"]["provider_name"], "yahoo")
        self.assertEqual(job.metadata["provider_failure"]["workflow"], "backtest")


class BacktestApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="analyst", password="secret-pass-123")
        self.client.force_login(self.user)
        self.workspace = self.user.workspace_memberships.get().workspace
        self.universe = Universe.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Web Backtest Universe",
            source_type=Universe.SourceType.MANUAL,
            entry_count=2,
        )
        self.universe.entries.create(position=1, raw_ticker="AAA", normalized_ticker="AAA")
        self.universe.entries.create(position=2, raw_ticker="BBB", normalized_ticker="BBB")

    @patch("apps.backtests.tasks.run_backtest_job.apply_async")
    def test_launch_list_and_detail_backtest_run(self, apply_async) -> None:
        apply_async.return_value = SimpleNamespace(id="backtest-task-123")

        response = self.client.post(
            "/api/v1/backtests/",
            data={
                "workspace_id": self.workspace.id,
                "universe_id": self.universe.id,
                "start_date": "2024-01-05",
                "end_date": "2025-02-14",
                "portfolio_size": 10,
                "benchmark": "^GSPC",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["job"]["state"], JobRun.State.QUEUED)
        self.assertEqual(payload["job"]["celery_task_id"], "backtest-task-123")
        self.assertEqual(payload["universe"]["id"], self.universe.id)

        listing = self.client.get(f"/api/v1/backtests/?workspace_id={self.workspace.id}")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)
        self.assertEqual(len(listing.json()["results"]), 1)

        detail = self.client.get(f"/api/v1/backtests/{payload['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], payload["id"])

        updated = self.client.patch(
            f"/api/v1/backtests/{payload['id']}/",
            data={"is_starred": True, "tags": ["baseline"], "notes": "Retest after provider refresh."},
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.json()["is_starred"])
        self.assertEqual(updated.json()["tags"], ["baseline"])
        self.assertEqual(updated.json()["notes"], "Retest after provider refresh.")

        starred_listing = self.client.get(f"/api/v1/backtests/?workspace_id={self.workspace.id}&starred_only=true")
        self.assertEqual(starred_listing.status_code, 200)
        self.assertEqual(starred_listing.json()["count"], 1)

    def test_child_data_and_export_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(ARTIFACT_STORAGE_ROOT=temp_dir):
                job = JobRun.objects.create(
                    workspace=self.workspace,
                    created_by=self.user,
                    job_type="backtest_run",
                    state=JobRun.State.SUCCEEDED,
                    progress_percent=100,
                    current_step="Completed",
                )
                backtest_run = BacktestRun.objects.create(
                    workspace=self.workspace,
                    created_by=self.user,
                    universe=self.universe,
                    job=job,
                    start_date=date(2024, 1, 5),
                    end_date=date(2025, 2, 14),
                    initial_capital=100000,
                    portfolio_size=2,
                    benchmark="^GSPC",
                    equity_point_count=2,
                    trade_count=2,
                    review_target_count=1,
                    final_holding_count=1,
                    summary={"total_return": 0.12, "ending_equity": 112000},
                )
                BacktestEquityPoint.objects.create(
                    backtest_run=backtest_run,
                    position=1,
                    date=date(2024, 1, 5),
                    cash=0,
                    equity=100000,
                    positions=2,
                    benchmark_equity=100000,
                )
                BacktestEquityPoint.objects.create(
                    backtest_run=backtest_run,
                    position=2,
                    date=date(2025, 2, 14),
                    cash=1000,
                    equity=112000,
                    positions=2,
                    benchmark_equity=110000,
                )
                BacktestTrade.objects.create(
                    backtest_run=backtest_run,
                    position=1,
                    date=date(2024, 1, 5),
                    ticker="AAA",
                    side="BUY",
                    shares=10,
                    price=100,
                    proceeds=1000,
                    reason="initial allocation",
                )
                BacktestTrade.objects.create(
                    backtest_run=backtest_run,
                    position=2,
                    date=date(2024, 1, 12),
                    ticker="BBB",
                    side="SELL",
                    shares=10,
                    price=110,
                    proceeds=1100,
                    reason="rebalance replacement",
                )
                BacktestReviewTarget.objects.create(
                    backtest_run=backtest_run,
                    position=1,
                    date=date(2024, 1, 5),
                    target_rank=1,
                    ticker="AAA",
                    company_name="AAA",
                    final_score=1,
                )
                BacktestFinalHolding.objects.create(
                    backtest_run=backtest_run,
                    position=1,
                    ticker="AAA",
                    shares=12,
                    entry_date=date(2024, 1, 5),
                    entry_price=100,
                    score=1,
                )
                stored = ArtifactStorage(root=temp_dir).store_artifact(
                    workspace=self.workspace,
                    category="backtests",
                    original_filename="backtest-artifacts.zip",
                    content=b"PK\x03\x04demo",
                )
                backtest_run.export_storage_backend = stored.storage_backend
                backtest_run.export_storage_key = stored.storage_key
                backtest_run.export_filename = "backtest-artifacts.zip"
                backtest_run.export_checksum_sha256 = stored.checksum_sha256
                backtest_run.export_size_bytes = stored.size_bytes
                backtest_run.save()

                equity = self.client.get(f"/api/v1/backtests/{backtest_run.id}/equity/")
                self.assertEqual(equity.status_code, 200)
                self.assertEqual(equity.json()["count"], 2)

                trades = self.client.get(f"/api/v1/backtests/{backtest_run.id}/trades/?sort=date&direction=desc&page_size=1")
                self.assertEqual(trades.status_code, 200)
                self.assertEqual(trades.json()["results"][0]["ticker"], "BBB")

                review_targets = self.client.get(f"/api/v1/backtests/{backtest_run.id}/review-targets/")
                self.assertEqual(review_targets.status_code, 200)
                self.assertEqual(review_targets.json()["results"][0]["ticker"], "AAA")

                holdings = self.client.get(f"/api/v1/backtests/{backtest_run.id}/final-holdings/")
                self.assertEqual(holdings.status_code, 200)
                self.assertEqual(holdings.json()["results"][0]["ticker"], "AAA")

                export_response = self.client.get(f"/api/v1/backtests/{backtest_run.id}/export/")
                self.assertEqual(export_response.status_code, 200)
                self.assertEqual(export_response.headers["Content-Disposition"], 'attachment; filename="backtest-artifacts.zip"')

                export_json = self.client.get(f"/api/v1/backtests/{backtest_run.id}/export/json/")
                self.assertEqual(export_json.status_code, 200)
                self.assertEqual(export_json.json()["run"]["workflow_kind"], "backtest")
                self.assertEqual(len(export_json.json()["equity_points"]), 2)

    def test_viewer_cannot_launch_backtest(self) -> None:
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
            "/api/v1/backtests/",
            data={"workspace_id": workspace.id, "universe_id": universe.id, "start_date": "2024-01-05", "end_date": "2025-02-14"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
