from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.backtests.models import BacktestRun
from apps.jobs.models import JobRun
from apps.screens.models import ScreenRun
from apps.strategy_templates.models import StrategyTemplate
from apps.universes.models import Universe


User = get_user_model()


class StrategyTemplateApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="templater", password="secret-pass-123")
        self.client.force_login(self.user)
        self.workspace = self.user.workspace_memberships.get().workspace
        self.universe = Universe.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Template Universe",
            source_type=Universe.SourceType.MANUAL,
            entry_count=2,
        )
        self.universe.entries.create(position=1, raw_ticker="AAA", normalized_ticker="AAA")
        self.universe.entries.create(position=2, raw_ticker="BBB", normalized_ticker="BBB")

    def _screen_run(self) -> ScreenRun:
        job = JobRun.objects.create(workspace=self.workspace, created_by=self.user, job_type="screen_run")
        return ScreenRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            universe=self.universe,
            job=job,
            top_n=40,
            momentum_mode="overlay",
            sector_allowlist=["Technology"],
            min_market_cap=5_000_000_000,
        )

    def _backtest_run(self) -> BacktestRun:
        job = JobRun.objects.create(workspace=self.workspace, created_by=self.user, job_type="backtest_run")
        return BacktestRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            universe=self.universe,
            job=job,
            start_date=date(2024, 1, 5),
            end_date=date(2025, 2, 14),
            portfolio_size=12,
            benchmark="^GSPC",
        )

    def test_create_template_from_screen_run_and_update_it(self) -> None:
        screen_run = self._screen_run()

        response = self.client.post(
            "/api/v1/strategy-templates/",
            data={
                "name": "Growth Screen",
                "description": "Saved from run",
                "source_screen_run_id": screen_run.id,
                "is_starred": True,
                "tags": ["favorite"],
                "notes": "Use for recurring review.",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["workflow_kind"], StrategyTemplate.WorkflowKind.SCREEN)
        self.assertEqual(payload["config"]["top_n"], 40)
        self.assertEqual(payload["source_screen_run_id"], screen_run.id)
        self.assertTrue(payload["is_starred"])
        self.assertEqual(payload["tags"], ["favorite"])
        self.assertEqual(payload["notes"], "Use for recurring review.")

        template_id = payload["id"]
        updated = self.client.patch(
            f"/api/v1/strategy-templates/{template_id}/",
            data={"name": "Updated Growth Screen", "description": "Edited", "tags": ["favorite", "screen"], "notes": "Promoted after review."},
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["name"], "Updated Growth Screen")
        self.assertEqual(updated.json()["tags"], ["favorite", "screen"])
        self.assertEqual(updated.json()["notes"], "Promoted after review.")

        listing = self.client.get(f"/api/v1/strategy-templates/?workspace_id={self.workspace.id}&starred_only=true")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)

    @patch("apps.screens.tasks.run_screen_job.apply_async")
    def test_launch_screen_template(self, apply_async) -> None:
        apply_async.return_value = SimpleNamespace(id="screen-template-task")
        template = StrategyTemplate.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Template",
            workflow_kind=StrategyTemplate.WorkflowKind.SCREEN,
            universe=self.universe,
            config={
                "top_n": 25,
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

        response = self.client.post(f"/api/v1/strategy-templates/{template.id}/launch/")

        self.assertEqual(response.status_code, 202)
        payload = response.json()
        self.assertEqual(payload["workflow_kind"], "screen")
        self.assertEqual(payload["run"]["job"]["celery_task_id"], "screen-template-task")

    @patch("apps.backtests.tasks.run_backtest_job.apply_async")
    def test_launch_backtest_template_and_delete_it(self, apply_async) -> None:
        apply_async.return_value = SimpleNamespace(id="backtest-template-task")
        template = StrategyTemplate.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Backtest Template",
            workflow_kind=StrategyTemplate.WorkflowKind.BACKTEST,
            universe=self.universe,
            config={
                "start_date": "2024-01-05",
                "end_date": "2025-02-14",
                "initial_capital": 100000.0,
                "portfolio_size": 10,
                "review_frequency": "W-FRI",
                "benchmark": "^GSPC",
                "momentum_mode": "none",
                "sector_allowlist": [],
                "min_market_cap": None,
                "use_cache": True,
                "refresh_cache": False,
                "cache_ttl_hours": 24.0,
            },
        )

        launch = self.client.post(f"/api/v1/strategy-templates/{template.id}/launch/")
        self.assertEqual(launch.status_code, 202)
        self.assertEqual(launch.json()["workflow_kind"], "backtest")

        listing = self.client.get(f"/api/v1/strategy-templates/?workspace_id={self.workspace.id}&workflow_kind=backtest")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)

        delete = self.client.delete(f"/api/v1/strategy-templates/{template.id}/")
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(StrategyTemplate.objects.filter(pk=template.id).exists())
