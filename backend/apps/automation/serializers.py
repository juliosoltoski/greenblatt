from __future__ import annotations

import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers

from apps.automation.models import AlertRule, NotificationEvent, RunSchedule
from apps.collaboration.models import ReviewStatus


CRON_FIELD_PATTERN = re.compile(r"^[A-Za-z0-9_*/,\-]+$")


def _validate_cron_field(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise serializers.ValidationError(f"{field_name} cannot be blank.")
    if not CRON_FIELD_PATTERN.fullmatch(cleaned):
        raise serializers.ValidationError(f"{field_name} contains unsupported characters.")
    return cleaned


class PaginationSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class RunScheduleListSerializer(PaginationSerializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    is_enabled = serializers.BooleanField(required=False)


class RunScheduleCreateSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    strategy_template_id = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    timezone = serializers.CharField(required=False, max_length=64)
    cron_minute = serializers.CharField(required=False, default="0", max_length=64)
    cron_hour = serializers.CharField(required=False, default="13", max_length=64)
    cron_day_of_week = serializers.CharField(required=False, default="1-5", max_length=64)
    cron_day_of_month = serializers.CharField(required=False, default="*", max_length=64)
    cron_month_of_year = serializers.CharField(required=False, default="*", max_length=64)
    is_enabled = serializers.BooleanField(required=False, default=True)
    notify_channel = serializers.ChoiceField(
        choices=RunSchedule.NotificationChannel.choices,
        required=False,
        default=RunSchedule.NotificationChannel.EMAIL,
    )
    notify_email = serializers.EmailField(required=False, allow_blank=True, default="")
    notify_webhook_url = serializers.URLField(required=False, allow_blank=True, default="")
    notify_on_success = serializers.BooleanField(required=False, default=True)
    notify_on_failure = serializers.BooleanField(required=False, default=True)
    review_status = serializers.ChoiceField(choices=ReviewStatus.choices, required=False, default=ReviewStatus.DRAFT)
    review_notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_timezone(self, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError("Unknown timezone.") from exc
        return value

    def validate_cron_minute(self, value: str) -> str:
        return _validate_cron_field(value, "cron_minute")

    def validate_cron_hour(self, value: str) -> str:
        return _validate_cron_field(value, "cron_hour")

    def validate_cron_day_of_week(self, value: str) -> str:
        return _validate_cron_field(value, "cron_day_of_week")

    def validate_cron_day_of_month(self, value: str) -> str:
        return _validate_cron_field(value, "cron_day_of_month")

    def validate_cron_month_of_year(self, value: str) -> str:
        return _validate_cron_field(value, "cron_month_of_year")

    def validate(self, attrs):
        channel = attrs.get("notify_channel", RunSchedule.NotificationChannel.EMAIL)
        attrs["notify_email"] = attrs.get("notify_email", "").strip()
        attrs["notify_webhook_url"] = attrs.get("notify_webhook_url", "").strip()
        if channel == RunSchedule.NotificationChannel.EMAIL:
            attrs["notify_webhook_url"] = attrs.get("notify_webhook_url", "")
        return attrs


class RunScheduleUpdateSerializer(RunScheduleCreateSerializer):
    strategy_template_id = serializers.IntegerField(required=False, min_value=1)
    name = serializers.CharField(required=False, max_length=255)


class AlertRuleListSerializer(PaginationSerializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    event_type = serializers.ChoiceField(choices=AlertRule.EventType.choices, required=False)
    is_enabled = serializers.BooleanField(required=False)


class AlertRuleCreateSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    event_type = serializers.ChoiceField(choices=AlertRule.EventType.choices)
    workflow_kind = serializers.ChoiceField(
        choices=AlertRule.WorkflowKind.choices,
        required=False,
        allow_blank=True,
        default=AlertRule.WorkflowKind.ANY,
    )
    channel = serializers.ChoiceField(choices=AlertRule.Channel.choices, required=False, default=AlertRule.Channel.EMAIL)
    strategy_template_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    destination_email = serializers.EmailField(required=False, allow_blank=True, default="")
    destination_webhook_url = serializers.URLField(required=False, allow_blank=True, default="")
    ticker = serializers.CharField(required=False, allow_blank=True, max_length=32, default="")
    top_n_threshold = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=500)
    is_enabled = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        event_type = attrs["event_type"]
        workflow_kind = attrs.get("workflow_kind", AlertRule.WorkflowKind.ANY)
        ticker = attrs.get("ticker", "").strip().upper()
        threshold = attrs.get("top_n_threshold")

        if event_type == AlertRule.EventType.SCREEN_COMPLETED and workflow_kind == AlertRule.WorkflowKind.ANY:
            attrs["workflow_kind"] = AlertRule.WorkflowKind.SCREEN
        if event_type == AlertRule.EventType.BACKTEST_COMPLETED and workflow_kind == AlertRule.WorkflowKind.ANY:
            attrs["workflow_kind"] = AlertRule.WorkflowKind.BACKTEST
        if event_type == AlertRule.EventType.TICKER_ENTERED_TOP_N:
            attrs["workflow_kind"] = AlertRule.WorkflowKind.SCREEN
            if not ticker:
                raise serializers.ValidationError({"ticker": "Ticker is required for top-N alerts."})
            if threshold is None:
                raise serializers.ValidationError({"top_n_threshold": "A top-N threshold is required for this alert."})
        else:
            attrs["ticker"] = ticker
        attrs["destination_email"] = attrs.get("destination_email", "").strip()
        attrs["destination_webhook_url"] = attrs.get("destination_webhook_url", "").strip()
        attrs["ticker"] = ticker
        return attrs


class AlertRuleUpdateSerializer(AlertRuleCreateSerializer):
    name = serializers.CharField(required=False, max_length=255)
    event_type = serializers.ChoiceField(choices=AlertRule.EventType.choices, required=False)

    def validate(self, attrs):
        base = {
            "event_type": getattr(self.instance, "event_type", None),
            "workflow_kind": getattr(self.instance, "workflow_kind", AlertRule.WorkflowKind.ANY),
            "ticker": getattr(self.instance, "ticker", ""),
            "top_n_threshold": getattr(self.instance, "top_n_threshold", None),
            **attrs,
        }
        return super().validate(base)


class NotificationEventListSerializer(PaginationSerializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(choices=[("", "Any"), *NotificationEvent.Status.choices], required=False)


class WorkspaceNotificationPreferenceSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    default_email = serializers.EmailField(required=False, allow_blank=True)
    email_enabled = serializers.BooleanField(required=False)
    slack_enabled = serializers.BooleanField(required=False)
    webhook_enabled = serializers.BooleanField(required=False)
    slack_webhook_url = serializers.URLField(required=False, allow_blank=True)
    generic_webhook_url = serializers.URLField(required=False, allow_blank=True)
    digest_enabled = serializers.BooleanField(required=False)
    digest_hour_utc = serializers.IntegerField(required=False, min_value=0, max_value=23)
    notify_on_run_success = serializers.BooleanField(required=False)
    notify_on_run_failure = serializers.BooleanField(required=False)


class UserNotificationPreferenceSerializer(serializers.Serializer):
    workspace_id = serializers.IntegerField(required=False, min_value=1)
    delivery_email = serializers.EmailField(required=False, allow_blank=True)
    email_enabled = serializers.BooleanField(required=False)
    slack_enabled = serializers.BooleanField(required=False)
    webhook_enabled = serializers.BooleanField(required=False)
    digest_enabled = serializers.BooleanField(required=False)
