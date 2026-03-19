from __future__ import annotations

from apps.automation.models import AlertRule, NotificationEvent, RunSchedule, UserNotificationPreference, WorkspaceNotificationPreference
from apps.strategy_templates.presenters import serialize_strategy_template
from apps.workspaces.presenters import serialize_workspace


def serialize_run_schedule(schedule: RunSchedule) -> dict[str, object | None]:
    periodic_task = schedule.periodic_task
    return {
        "id": schedule.id,
        "workspace": serialize_workspace(schedule.workspace),
        "created_by_id": schedule.created_by_id,
        "strategy_template": serialize_strategy_template(schedule.strategy_template),
        "name": schedule.name,
        "description": schedule.description,
        "timezone": schedule.timezone,
        "cron_minute": schedule.cron_minute,
        "cron_hour": schedule.cron_hour,
        "cron_day_of_week": schedule.cron_day_of_week,
        "cron_day_of_month": schedule.cron_day_of_month,
        "cron_month_of_year": schedule.cron_month_of_year,
        "is_enabled": schedule.is_enabled,
        "notify_channel": schedule.notify_channel,
        "notify_email": schedule.notify_email,
        "notify_webhook_url": schedule.notify_webhook_url or None,
        "notify_on_success": schedule.notify_on_success,
        "notify_on_failure": schedule.notify_on_failure,
        "review_status": schedule.review_status,
        "reviewed_by_id": schedule.reviewed_by_id,
        "reviewed_at": schedule.reviewed_at.isoformat() if schedule.reviewed_at else None,
        "review_notes": schedule.review_notes,
        "periodic_task_id": schedule.periodic_task_id,
        "periodic_task_name": periodic_task.name if periodic_task else None,
        "periodic_task_enabled": periodic_task.enabled if periodic_task else None,
        "periodic_task_last_run_at": periodic_task.last_run_at.isoformat() if periodic_task and periodic_task.last_run_at else None,
        "last_triggered_at": schedule.last_triggered_at.isoformat() if schedule.last_triggered_at else None,
        "last_launch_status": schedule.last_launch_status or None,
        "last_run_workflow_kind": schedule.last_run_workflow_kind or None,
        "last_run_id": schedule.last_run_id,
        "last_job_run_id": schedule.last_job_run_id,
        "last_error_message": schedule.last_error_message or None,
        "created_at": schedule.created_at.isoformat(),
        "updated_at": schedule.updated_at.isoformat(),
    }


def serialize_alert_rule(rule: AlertRule) -> dict[str, object | None]:
    return {
        "id": rule.id,
        "workspace": serialize_workspace(rule.workspace),
        "created_by_id": rule.created_by_id,
        "strategy_template_id": rule.strategy_template_id,
        "name": rule.name,
        "description": rule.description,
        "event_type": rule.event_type,
        "workflow_kind": rule.workflow_kind,
        "channel": rule.channel,
        "destination_email": rule.destination_email,
        "destination_webhook_url": rule.destination_webhook_url or None,
        "ticker": rule.ticker or None,
        "top_n_threshold": rule.top_n_threshold,
        "is_enabled": rule.is_enabled,
        "last_triggered_at": rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }


def serialize_notification_event(event: NotificationEvent) -> dict[str, object | None]:
    return {
        "id": event.id,
        "workspace": serialize_workspace(event.workspace),
        "alert_rule_id": event.alert_rule_id,
        "run_schedule_id": event.run_schedule_id,
        "screen_run_id": event.screen_run_id,
        "backtest_run_id": event.backtest_run_id,
        "job_id": event.job_id,
        "channel": event.channel,
        "event_type": event.event_type,
        "status": event.status,
        "recipient_email": event.recipient_email or None,
        "recipient_webhook_url": event.recipient_webhook_url or None,
        "subject": event.subject,
        "body": event.body,
        "delivery_error": event.delivery_error or None,
        "metadata": event.metadata,
        "sent_at": event.sent_at.isoformat() if event.sent_at else None,
        "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(),
    }


def serialize_workspace_notification_preference(preference: WorkspaceNotificationPreference) -> dict[str, object | None]:
    return {
        "workspace": serialize_workspace(preference.workspace),
        "default_email": preference.default_email,
        "email_enabled": preference.email_enabled,
        "slack_enabled": preference.slack_enabled,
        "webhook_enabled": preference.webhook_enabled,
        "slack_webhook_url": preference.slack_webhook_url or None,
        "generic_webhook_url": preference.generic_webhook_url or None,
        "digest_enabled": preference.digest_enabled,
        "digest_hour_utc": preference.digest_hour_utc,
        "notify_on_run_success": preference.notify_on_run_success,
        "notify_on_run_failure": preference.notify_on_run_failure,
        "last_digest_sent_at": preference.last_digest_sent_at.isoformat() if preference.last_digest_sent_at else None,
        "created_at": preference.created_at.isoformat(),
        "updated_at": preference.updated_at.isoformat(),
    }


def serialize_user_notification_preference(preference: UserNotificationPreference) -> dict[str, object | None]:
    return {
        "workspace": serialize_workspace(preference.workspace),
        "user_id": preference.user_id,
        "delivery_email": preference.delivery_email,
        "email_enabled": preference.email_enabled,
        "slack_enabled": preference.slack_enabled,
        "webhook_enabled": preference.webhook_enabled,
        "digest_enabled": preference.digest_enabled,
        "created_at": preference.created_at.isoformat(),
        "updated_at": preference.updated_at.isoformat(),
    }
