from __future__ import annotations

from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.collaboration.models import ReviewStatus
from apps.collaboration.services import record_activity
from apps.core.throttling import LaunchRateThrottle, MethodScopedThrottleMixin, MutationRateThrottle
from apps.automation.models import AlertRule, NotificationEvent, RunSchedule
from apps.automation.presenters import (
    serialize_alert_rule,
    serialize_notification_event,
    serialize_run_schedule,
    serialize_user_notification_preference,
    serialize_workspace_notification_preference,
)
from apps.automation.serializers import (
    AlertRuleCreateSerializer,
    AlertRuleListSerializer,
    AlertRuleUpdateSerializer,
    NotificationEventListSerializer,
    RunScheduleCreateSerializer,
    RunScheduleListSerializer,
    RunScheduleUpdateSerializer,
    UserNotificationPreferenceSerializer,
    WorkspaceNotificationPreferenceSerializer,
)
from apps.automation.services import AlertRuleDefinition, AlertRuleService, NotificationService, RunScheduleDefinition, ScheduleService
from apps.backtests.presenters import serialize_backtest_run
from apps.screens.presenters import serialize_screen_run
from apps.strategy_templates.models import StrategyTemplate
from apps.workspaces.access import accessible_workspace_ids, require_workspace_role, resolve_workspace_for_request


def _paginate_queryset(queryset, *, page: int, page_size: int):
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    return paginator, page_obj


def _schedule_queryset(user):
    return (
        RunSchedule.objects.select_related(
            "workspace",
            "workspace__owner",
            "created_by",
            "strategy_template",
            "strategy_template__workspace",
            "strategy_template__created_by",
            "strategy_template__universe",
            "strategy_template__universe__workspace",
            "strategy_template__universe__source_upload",
            "periodic_task",
        )
        .prefetch_related("strategy_template__universe__entries")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


def _template_queryset(user):
    return (
        StrategyTemplate.objects.select_related(
            "workspace",
            "created_by",
            "universe",
            "universe__workspace",
            "universe__source_upload",
        )
        .prefetch_related("universe__entries")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


def _alert_rule_queryset(user):
    return (
        AlertRule.objects.select_related("workspace", "workspace__owner", "created_by", "strategy_template")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


def _notification_queryset(user):
    return (
        NotificationEvent.objects.select_related("workspace", "alert_rule", "run_schedule")
        .filter(workspace_id__in=accessible_workspace_ids(user))
    )


class RunScheduleListCreateView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [MutationRateThrottle],
    }

    def get(self, request):
        serializer = RunScheduleListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        queryset = _schedule_queryset(request.user).filter(workspace=workspace)
        if "is_enabled" in request.query_params:
            queryset = queryset.filter(is_enabled=serializer.validated_data["is_enabled"])
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "workspace_id": workspace.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "results": [serialize_run_schedule(schedule) for schedule in page_obj.object_list],
            }
        )

    def post(self, request):
        serializer = RunScheduleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = get_object_or_404(_template_queryset(request.user), pk=serializer.validated_data["strategy_template_id"])
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id") or template.workspace_id)
        if template.workspace_id != workspace.id:
            return Response({"detail": "Template does not belong to the requested workspace."}, status=status.HTTP_400_BAD_REQUEST)
        require_workspace_role(request.user, workspace, "analyst", "You need analyst access or higher to manage schedules.")
        review_status = serializer.validated_data.get("review_status", ReviewStatus.DRAFT)
        if review_status in {ReviewStatus.APPROVED, ReviewStatus.CHANGES_REQUESTED}:
            require_workspace_role(
                request.user,
                workspace,
                "admin",
                "You do not have permission to create a schedule directly in that review state.",
            )
        schedule = ScheduleService().create_schedule(
            RunScheduleDefinition(
                workspace=workspace,
                created_by=request.user,
                strategy_template=template,
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                timezone=serializer.validated_data.get("timezone") or workspace.timezone,
                cron_minute=serializer.validated_data["cron_minute"],
                cron_hour=serializer.validated_data["cron_hour"],
                cron_day_of_week=serializer.validated_data["cron_day_of_week"],
                cron_day_of_month=serializer.validated_data["cron_day_of_month"],
                cron_month_of_year=serializer.validated_data["cron_month_of_year"],
                is_enabled=serializer.validated_data["is_enabled"],
                notify_channel=serializer.validated_data.get("notify_channel", RunSchedule.NotificationChannel.EMAIL),
                notify_email=serializer.validated_data.get("notify_email", ""),
                notify_webhook_url=serializer.validated_data.get("notify_webhook_url", ""),
                notify_on_success=serializer.validated_data["notify_on_success"],
                notify_on_failure=serializer.validated_data["notify_on_failure"],
                review_status=review_status,
                review_notes=serializer.validated_data.get("review_notes", ""),
            )
        )
        if review_status != ReviewStatus.DRAFT or serializer.validated_data.get("review_notes", ""):
            schedule.reviewed_by = request.user
            schedule.reviewed_at = timezone.now()
            schedule.save(update_fields=["reviewed_by", "reviewed_at", "updated_at"])
        return Response(serialize_run_schedule(schedule), status=status.HTTP_201_CREATED)


class RunScheduleDetailView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "PATCH": [MutationRateThrottle],
        "DELETE": [MutationRateThrottle],
    }

    def get(self, request, schedule_id: int):
        schedule = get_object_or_404(_schedule_queryset(request.user), pk=schedule_id)
        return Response(serialize_run_schedule(schedule))

    def patch(self, request, schedule_id: int):
        schedule = get_object_or_404(_schedule_queryset(request.user), pk=schedule_id)
        require_workspace_role(request.user, schedule.workspace, "analyst", "You need analyst access or higher to manage schedules.")
        serializer = RunScheduleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        template = None
        if "strategy_template_id" in serializer.validated_data:
            template = get_object_or_404(_template_queryset(request.user), pk=serializer.validated_data["strategy_template_id"])
            if template.workspace_id != schedule.workspace_id:
                return Response({"detail": "Template does not belong to the schedule workspace."}, status=status.HTTP_400_BAD_REQUEST)
        review_status = serializer.validated_data.get("review_status")
        review_notes = serializer.validated_data.get("review_notes")
        reviewed_by = None
        reviewed_at = None
        if review_status is not None:
            minimum_role = "admin" if review_status in {ReviewStatus.APPROVED, ReviewStatus.CHANGES_REQUESTED} else "analyst"
            require_workspace_role(
                request.user,
                schedule.workspace,
                minimum_role,
                "You do not have permission to move this schedule into the requested review state.",
            )
            reviewed_by = request.user
            reviewed_at = timezone.now()
        elif review_notes is not None:
            reviewed_by = request.user
            reviewed_at = timezone.now()
        updated = ScheduleService().update_schedule(
            schedule,
            strategy_template=template,
            name=serializer.validated_data.get("name"),
            description=serializer.validated_data.get("description"),
            timezone=serializer.validated_data.get("timezone"),
            cron_minute=serializer.validated_data.get("cron_minute"),
            cron_hour=serializer.validated_data.get("cron_hour"),
            cron_day_of_week=serializer.validated_data.get("cron_day_of_week"),
            cron_day_of_month=serializer.validated_data.get("cron_day_of_month"),
            cron_month_of_year=serializer.validated_data.get("cron_month_of_year"),
            is_enabled=serializer.validated_data.get("is_enabled"),
            notify_channel=serializer.validated_data.get("notify_channel"),
            notify_email=serializer.validated_data.get("notify_email"),
            notify_webhook_url=serializer.validated_data.get("notify_webhook_url"),
            notify_on_success=serializer.validated_data.get("notify_on_success"),
            notify_on_failure=serializer.validated_data.get("notify_on_failure"),
            review_status=review_status,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            review_notes=review_notes,
        )
        if review_status is not None or review_notes is not None:
            record_activity(
                workspace=updated.workspace,
                actor=request.user,
                resource_kind="run_schedule",
                resource_id=updated.id,
                verb="review_updated",
                summary=f"Updated review state for schedule '{updated.name}'.",
                metadata={"review_status": updated.review_status},
            )
        return Response(serialize_run_schedule(updated))

    def delete(self, request, schedule_id: int):
        schedule = get_object_or_404(_schedule_queryset(request.user), pk=schedule_id)
        require_workspace_role(request.user, schedule.workspace, "analyst", "You need analyst access or higher to manage schedules.")
        ScheduleService().delete_schedule(schedule)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RunScheduleTriggerView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [LaunchRateThrottle],
    }

    def post(self, request, schedule_id: int):
        schedule = get_object_or_404(_schedule_queryset(request.user), pk=schedule_id)
        require_workspace_role(request.user, schedule.workspace, "analyst", "You need analyst access or higher to trigger schedules.")
        run = ScheduleService().launch_schedule(schedule, trigger_source="manual_schedule_trigger")
        response_status = status.HTTP_202_ACCEPTED if run.job.state == run.job.State.QUEUED else status.HTTP_503_SERVICE_UNAVAILABLE
        if schedule.strategy_template.workflow_kind == StrategyTemplate.WorkflowKind.SCREEN:
            return Response({"workflow_kind": "screen", "run": serialize_screen_run(run)}, status=response_status)
        return Response({"workflow_kind": "backtest", "run": serialize_backtest_run(run)}, status=response_status)


class AlertRuleListCreateView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "POST": [MutationRateThrottle],
    }

    def get(self, request):
        serializer = AlertRuleListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        queryset = _alert_rule_queryset(request.user).filter(workspace=workspace)
        if "event_type" in serializer.validated_data:
            queryset = queryset.filter(event_type=serializer.validated_data["event_type"])
        if "is_enabled" in request.query_params:
            queryset = queryset.filter(is_enabled=serializer.validated_data["is_enabled"])
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "workspace_id": workspace.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "results": [serialize_alert_rule(rule) for rule in page_obj.object_list],
            }
        )

    def post(self, request):
        serializer = AlertRuleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        require_workspace_role(request.user, workspace, "analyst", "You need analyst access or higher to manage alerts.")
        template = None
        if serializer.validated_data.get("strategy_template_id") is not None:
            template = get_object_or_404(_template_queryset(request.user), pk=serializer.validated_data["strategy_template_id"])
            if template.workspace_id != workspace.id:
                return Response({"detail": "Template does not belong to the requested workspace."}, status=status.HTTP_400_BAD_REQUEST)
        rule = AlertRuleService().create_rule(
            AlertRuleDefinition(
                workspace=workspace,
                created_by=request.user,
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
                event_type=serializer.validated_data["event_type"],
                workflow_kind=serializer.validated_data.get("workflow_kind", ""),
                channel=serializer.validated_data.get("channel", AlertRule.Channel.EMAIL),
                destination_email=serializer.validated_data.get("destination_email", ""),
                destination_webhook_url=serializer.validated_data.get("destination_webhook_url", ""),
                ticker=serializer.validated_data.get("ticker", ""),
                top_n_threshold=serializer.validated_data.get("top_n_threshold"),
                is_enabled=serializer.validated_data["is_enabled"],
                strategy_template=template,
            )
        )
        return Response(serialize_alert_rule(rule), status=status.HTTP_201_CREATED)


class AlertRuleDetailView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "PATCH": [MutationRateThrottle],
        "DELETE": [MutationRateThrottle],
    }

    def get(self, request, rule_id: int):
        rule = get_object_or_404(_alert_rule_queryset(request.user), pk=rule_id)
        return Response(serialize_alert_rule(rule))

    def patch(self, request, rule_id: int):
        rule = get_object_or_404(_alert_rule_queryset(request.user), pk=rule_id)
        require_workspace_role(request.user, rule.workspace, "analyst", "You need analyst access or higher to manage alerts.")
        serializer = AlertRuleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        template = rule.strategy_template
        if "strategy_template_id" in serializer.validated_data:
            strategy_template_id = serializer.validated_data["strategy_template_id"]
            if strategy_template_id is None:
                template = None
            else:
                template = get_object_or_404(_template_queryset(request.user), pk=strategy_template_id)
                if template.workspace_id != rule.workspace_id:
                    return Response({"detail": "Template does not belong to the alert workspace."}, status=status.HTTP_400_BAD_REQUEST)
        updated = AlertRuleService().update_rule(
            rule,
            strategy_template=template,
            name=serializer.validated_data.get("name"),
            description=serializer.validated_data.get("description"),
            event_type=serializer.validated_data.get("event_type"),
            workflow_kind=serializer.validated_data.get("workflow_kind"),
            channel=serializer.validated_data.get("channel"),
            destination_email=serializer.validated_data.get("destination_email"),
            destination_webhook_url=serializer.validated_data.get("destination_webhook_url"),
            ticker=serializer.validated_data.get("ticker"),
            top_n_threshold=serializer.validated_data.get("top_n_threshold"),
            is_enabled=serializer.validated_data.get("is_enabled"),
        )
        return Response(serialize_alert_rule(updated))

    def delete(self, request, rule_id: int):
        rule = get_object_or_404(_alert_rule_queryset(request.user), pk=rule_id)
        require_workspace_role(request.user, rule.workspace, "analyst", "You need analyst access or higher to manage alerts.")
        rule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationEventListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = NotificationEventListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        queryset = _notification_queryset(request.user).filter(workspace=workspace)
        status_filter = serializer.validated_data.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        paginator, page_obj = _paginate_queryset(
            queryset,
            page=serializer.validated_data["page"],
            page_size=serializer.validated_data["page_size"],
        )
        return Response(
            {
                "workspace_id": workspace.id,
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": serializer.validated_data["page_size"],
                "results": [serialize_notification_event(event) for event in page_obj.object_list],
            }
        )


class WorkspaceNotificationPreferenceView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "PATCH": [MutationRateThrottle],
    }

    def get(self, request):
        serializer = WorkspaceNotificationPreferenceSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        preference = NotificationService().workspace_preferences(workspace)
        return Response(serialize_workspace_notification_preference(preference))

    def patch(self, request):
        serializer = WorkspaceNotificationPreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        require_workspace_role(
            request.user,
            workspace,
            "admin",
            "You need admin access or higher to update workspace notification preferences.",
        )
        preference = NotificationService().workspace_preferences(workspace)
        for field, value in serializer.validated_data.items():
            if field != "workspace_id":
                setattr(preference, field, value)
        preference.save()
        return Response(serialize_workspace_notification_preference(preference))


class UserNotificationPreferenceView(MethodScopedThrottleMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes_by_method = {
        "PATCH": [MutationRateThrottle],
    }

    def get(self, request):
        serializer = UserNotificationPreferenceSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        preference = NotificationService().user_preferences(workspace, request.user)
        if preference is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_user_notification_preference(preference))

    def patch(self, request):
        serializer = UserNotificationPreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        preference = NotificationService().user_preferences(workspace, request.user)
        if preference is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        for field, value in serializer.validated_data.items():
            if field != "workspace_id":
                setattr(preference, field, value)
        preference.save()
        return Response(serialize_user_notification_preference(preference))
