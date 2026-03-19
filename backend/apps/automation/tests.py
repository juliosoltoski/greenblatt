from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.automation.models import AlertRule, NotificationEvent, RunSchedule
from apps.collaboration.models import ReviewStatus
from apps.backtests.models import BacktestRun
from apps.jobs.models import JobRun
from apps.screens.models import ScreenResultRow, ScreenRun
from apps.screens.tasks import run_screen_job
from apps.strategy_templates.models import StrategyTemplate
from apps.universes.models import Universe
from apps.workspaces.models import WorkspaceMembership
from greenblatt.models import SecuritySnapshot
from greenblatt.providers.base import MarketDataProvider


User = get_user_model()


class FakeProvider(MarketDataProvider):
    supports_historical_fundamentals = False

    def __init__(self, snapshots: list[SecuritySnapshot]) -> None:
        self.snapshots = snapshots

    def get_snapshots(self, tickers, *, as_of=None, include_momentum=True):
        lookup = {snapshot.ticker: snapshot for snapshot in self.snapshots}
        return [lookup[ticker] for ticker in tickers if ticker in lookup]

    def get_price_history(self, tickers, *, start, end, interval="1d", auto_adjust=False):
        raise NotImplementedError

    def get_us_equity_candidates(self, *, limit: int = 3000):
        return [snapshot.ticker for snapshot in self.snapshots][:limit]


class FakeWebhookResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


def make_snapshot(ticker: str, rank_seed: int, *, momentum_6m: float | None = None) -> SecuritySnapshot:
    return SecuritySnapshot(
        ticker=ticker,
        company_name=f"{ticker} Holdings",
        sector="Technology",
        industry="Software",
        market_cap=200 - rank_seed,
        ebit=60 - rank_seed,
        current_assets=80,
        current_liabilities=20,
        cash_and_equivalents=10,
        total_debt=20,
        net_pp_e=60,
        momentum_6m=momentum_6m,
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AutomationApiTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username="scheduler",
            email="scheduler@example.com",
            password="secret-pass-123",
        )
        self.client.force_login(self.user)
        self.workspace = self.user.workspace_memberships.get().workspace
        self.universe = Universe.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Automation Universe",
            source_type=Universe.SourceType.MANUAL,
            entry_count=2,
        )
        self.universe.entries.create(position=1, raw_ticker="AAA", normalized_ticker="AAA")
        self.universe.entries.create(position=2, raw_ticker="BBB", normalized_ticker="BBB")
        self.screen_template = StrategyTemplate.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Weekly screen",
            workflow_kind=StrategyTemplate.WorkflowKind.SCREEN,
            universe=self.universe,
            config={
                "top_n": 20,
                "momentum_mode": "overlay",
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
        self.backtest_template = StrategyTemplate.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Monthly backtest",
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

    @patch("apps.screens.tasks.run_screen_job.apply_async")
    def test_create_schedule_and_trigger_it(self, apply_async) -> None:
        apply_async.return_value = SimpleNamespace(id="scheduled-screen-task")

        created = self.client.post(
            "/api/v1/automation/run-schedules/",
            data={
                "workspace_id": self.workspace.id,
                "strategy_template_id": self.screen_template.id,
                "name": "US weekly screen",
                "timezone": "UTC",
                "cron_minute": "30",
                "cron_hour": "14",
                "cron_day_of_week": "1-5",
                "notify_on_success": True,
                "notify_on_failure": True,
                "notify_email": "alerts@example.com",
            },
            content_type="application/json",
        )

        self.assertEqual(created.status_code, 201)
        payload = created.json()
        self.assertTrue(payload["periodic_task_id"])
        schedule = RunSchedule.objects.get(pk=payload["id"])
        self.assertTrue(PeriodicTask.objects.filter(pk=schedule.periodic_task_id, enabled=True).exists())

        listing = self.client.get(f"/api/v1/automation/run-schedules/?workspace_id={self.workspace.id}")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)

        trigger = self.client.post(f"/api/v1/automation/run-schedules/{schedule.id}/trigger/")
        self.assertEqual(trigger.status_code, 202)
        trigger_payload = trigger.json()
        self.assertEqual(trigger_payload["workflow_kind"], "screen")
        self.assertEqual(trigger_payload["run"]["job"]["celery_task_id"], "scheduled-screen-task")
        self.assertEqual(trigger_payload["run"]["source_template_id"], self.screen_template.id)

    def test_create_alert_rule_and_list_notifications(self) -> None:
        created = self.client.post(
            "/api/v1/automation/alert-rules/",
            data={
                "workspace_id": self.workspace.id,
                "name": "Alert on AAA",
                "event_type": "ticker_entered_top_n",
                "ticker": "aaa",
                "top_n_threshold": 10,
                "destination_email": "alerts@example.com",
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201)
        rule_id = created.json()["id"]
        self.assertEqual(created.json()["ticker"], "AAA")

        detail = self.client.get(f"/api/v1/automation/alert-rules/{rule_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["event_type"], "ticker_entered_top_n")

        notifications = self.client.get(f"/api/v1/automation/notification-events/?workspace_id={self.workspace.id}")
        self.assertEqual(notifications.status_code, 200)
        self.assertEqual(notifications.json()["count"], 0)

    def test_notification_preference_endpoints_round_trip(self) -> None:
        workspace_preference = self.client.get(f"/api/v1/automation/preferences/workspace/?workspace_id={self.workspace.id}")
        self.assertEqual(workspace_preference.status_code, 200)
        self.assertEqual(workspace_preference.json()["workspace"]["id"], self.workspace.id)

        updated_workspace = self.client.patch(
            "/api/v1/automation/preferences/workspace/",
            data={
                "workspace_id": self.workspace.id,
                "default_email": "team@example.com",
                "slack_webhook_url": "https://hooks.slack.test/services/demo",
                "digest_enabled": True,
                "digest_hour_utc": 7,
            },
            content_type="application/json",
        )
        self.assertEqual(updated_workspace.status_code, 200)
        self.assertEqual(updated_workspace.json()["default_email"], "team@example.com")
        self.assertTrue(updated_workspace.json()["digest_enabled"])

        user_preference = self.client.get(f"/api/v1/automation/preferences/me/?workspace_id={self.workspace.id}")
        self.assertEqual(user_preference.status_code, 200)
        self.assertEqual(user_preference.json()["user_id"], self.user.id)

        updated_user = self.client.patch(
            "/api/v1/automation/preferences/me/",
            data={
                "workspace_id": self.workspace.id,
                "delivery_email": "me@example.com",
                "slack_enabled": True,
            },
            content_type="application/json",
        )
        self.assertEqual(updated_user.status_code, 200)
        self.assertEqual(updated_user.json()["delivery_email"], "me@example.com")
        self.assertTrue(updated_user.json()["slack_enabled"])

    def test_digest_periodic_task_is_synced(self) -> None:
        from apps.automation.services import DIGEST_PERIODIC_TASK_NAME, NotificationService

        task = NotificationService().sync_system_tasks()

        self.assertEqual(task.name, DIGEST_PERIODIC_TASK_NAME)
        self.assertEqual(task.task, "automation.send_notification_digests")
        self.assertTrue(task.enabled)

    @patch("apps.screens.services.build_provider")
    def test_successful_screen_dispatch_sends_schedule_and_alert_notifications(self, provider_factory) -> None:
        provider_factory.return_value = FakeProvider(
            [
                make_snapshot("AAA", 1, momentum_6m=0.25),
                make_snapshot("BBB", 2, momentum_6m=0.10),
            ]
        )
        schedule = RunSchedule.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            strategy_template=self.screen_template,
            name="Daily screen",
            timezone="UTC",
            cron_minute="0",
            cron_hour="13",
            cron_day_of_week="1-5",
            cron_day_of_month="*",
            cron_month_of_year="*",
            notify_email="schedule@example.com",
            notify_on_success=True,
        )
        AlertRule.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="AAA top 5",
            event_type=AlertRule.EventType.TICKER_ENTERED_TOP_N,
            workflow_kind=AlertRule.WorkflowKind.SCREEN,
            destination_email="alerts@example.com",
            ticker="AAA",
            top_n_threshold=5,
        )
        job = JobRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            job_type="screen_run",
            metadata={
                "request": {"universe_id": self.universe.id},
                "run_schedule_id": schedule.id,
                "strategy_template_id": self.screen_template.id,
            },
        )
        screen_run = ScreenRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            source_template=self.screen_template,
            universe=self.universe,
            job=job,
            top_n=10,
            momentum_mode="overlay",
        )

        result = run_screen_job.apply(kwargs={"job_run_id": job.id, "screen_run_id": screen_run.id}, throw=False)

        self.assertTrue(result.successful())
        self.assertEqual(NotificationEvent.objects.count(), 2)
        recipients = sorted(event.recipient_email for event in NotificationEvent.objects.all())
        self.assertEqual(recipients, ["alerts@example.com", "schedule@example.com"])
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(any("AAA" in message.body for message in mail.outbox))

    def test_run_failed_alert_sends_email(self) -> None:
        AlertRule.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Any failure",
            event_type=AlertRule.EventType.RUN_FAILED,
            workflow_kind=AlertRule.WorkflowKind.BACKTEST,
            destination_email="alerts@example.com",
        )
        job = JobRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            job_type="backtest_run",
            state=JobRun.State.FAILED,
            error_message="Synthetic failure",
            metadata={"strategy_template_id": self.backtest_template.id},
        )
        backtest_run = BacktestRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            source_template=self.backtest_template,
            universe=self.universe,
            job=job,
            start_date=date(2024, 1, 5),
            end_date=date(2025, 2, 14),
            portfolio_size=10,
            benchmark="^GSPC",
        )

        from apps.automation.services import NotificationService

        NotificationService().dispatch_for_backtest_run(backtest_run)

        self.assertEqual(NotificationEvent.objects.count(), 1)
        event = NotificationEvent.objects.get()
        self.assertEqual(event.status, NotificationEvent.Status.SENT)
        self.assertEqual(event.recipient_email, "alerts@example.com")
        self.assertEqual(len(mail.outbox), 1)

    @patch("apps.automation.services.urllib_request.urlopen", return_value=FakeWebhookResponse())
    def test_run_failed_alert_can_send_webhook(self, urlopen_mock) -> None:
        AlertRule.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            name="Webhook failure",
            event_type=AlertRule.EventType.RUN_FAILED,
            workflow_kind=AlertRule.WorkflowKind.BACKTEST,
            channel=AlertRule.Channel.WEBHOOK,
            destination_webhook_url="https://example.test/hooks/general",
        )
        job = JobRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            job_type="backtest_run",
            state=JobRun.State.FAILED,
            error_message="Synthetic failure",
            metadata={"strategy_template_id": self.backtest_template.id},
        )
        backtest_run = BacktestRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            source_template=self.backtest_template,
            universe=self.universe,
            job=job,
            start_date=date(2024, 1, 5),
            end_date=date(2025, 2, 14),
            portfolio_size=10,
            benchmark="^GSPC",
        )

        from apps.automation.services import NotificationService

        NotificationService().dispatch_for_backtest_run(backtest_run)

        event = NotificationEvent.objects.get()
        self.assertEqual(event.channel, NotificationEvent.Channel.WEBHOOK)
        self.assertEqual(event.status, NotificationEvent.Status.SENT)
        self.assertEqual(event.recipient_webhook_url, "https://example.test/hooks/general")
        urlopen_mock.assert_called_once()

    def test_workspace_digest_sends_summary_email(self) -> None:
        from apps.automation.services import NotificationService

        workspace_preference = NotificationService().workspace_preferences(self.workspace)
        workspace_preference.digest_enabled = True
        workspace_preference.default_email = "digest@example.com"
        workspace_preference.digest_hour_utc = timezone.now().hour
        workspace_preference.save(update_fields=["digest_enabled", "default_email", "digest_hour_utc", "updated_at"])

        job = JobRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            job_type="screen_run",
            state=JobRun.State.SUCCEEDED,
            finished_at=timezone.now(),
        )
        ScreenRun.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            source_template=self.screen_template,
            universe=self.universe,
            job=job,
            top_n=10,
            momentum_mode="overlay",
            result_count=4,
        )

        sent_count = NotificationService().dispatch_workspace_digest(self.workspace, now=timezone.now())

        self.assertEqual(sent_count, 1)
        digest = NotificationEvent.objects.get(channel=NotificationEvent.Channel.DIGEST)
        self.assertEqual(digest.status, NotificationEvent.Status.SENT)
        self.assertEqual(digest.recipient_email, "digest@example.com")
        self.assertIn("Runs: 1 total", digest.body)
        self.assertEqual(len(mail.outbox), 1)
        workspace_preference.refresh_from_db()
        self.assertIsNotNone(workspace_preference.last_digest_sent_at)

        repeat_count = NotificationService().dispatch_workspace_digest(self.workspace, now=timezone.now())
        self.assertEqual(repeat_count, 0)
        self.assertEqual(NotificationEvent.objects.filter(channel=NotificationEvent.Channel.DIGEST).count(), 1)

    def test_schedule_review_status_can_be_updated(self) -> None:
        schedule = RunSchedule.objects.create(
            workspace=self.workspace,
            created_by=self.user,
            strategy_template=self.screen_template,
            name="Review me",
            review_status=ReviewStatus.DRAFT,
        )

        response = self.client.patch(
            f"/api/v1/automation/run-schedules/{schedule.id}/",
            data={"review_status": ReviewStatus.APPROVED, "review_notes": "Ready for recurring use."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["review_status"], ReviewStatus.APPROVED)
        self.assertEqual(response.json()["reviewed_by_id"], self.user.id)
        self.assertEqual(response.json()["review_notes"], "Ready for recurring use.")

    def test_viewer_cannot_manage_automation(self) -> None:
        owner = User.objects.create_user(username="owner", password="secret-pass-123")
        viewer = User.objects.create_user(username="viewer", password="secret-pass-123")
        workspace = owner.workspace_memberships.get().workspace
        WorkspaceMembership.objects.create(workspace=workspace, user=viewer, role=WorkspaceMembership.Role.VIEWER)
        owner_universe = Universe.objects.create(
            workspace=workspace,
            created_by=owner,
            name="Owner Universe",
            source_type=Universe.SourceType.MANUAL,
            entry_count=1,
        )
        owner_universe.entries.create(position=1, raw_ticker="AAA", normalized_ticker="AAA")
        template = StrategyTemplate.objects.create(
            workspace=workspace,
            created_by=owner,
            name="Owner screen",
            workflow_kind=StrategyTemplate.WorkflowKind.SCREEN,
            universe=owner_universe,
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
        self.client.force_login(viewer)

        response = self.client.post(
            "/api/v1/automation/run-schedules/",
            data={"workspace_id": workspace.id, "strategy_template_id": template.id, "name": "Nope"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
