from django.urls import path

from apps.automation.views import (
    AlertRuleDetailView,
    AlertRuleListCreateView,
    NotificationEventListView,
    RunScheduleDetailView,
    RunScheduleListCreateView,
    RunScheduleTriggerView,
    UserNotificationPreferenceView,
    WorkspaceNotificationPreferenceView,
)


urlpatterns = [
    path("run-schedules/", RunScheduleListCreateView.as_view(), name="run-schedule-list"),
    path("run-schedules/<int:schedule_id>/", RunScheduleDetailView.as_view(), name="run-schedule-detail"),
    path("run-schedules/<int:schedule_id>/trigger/", RunScheduleTriggerView.as_view(), name="run-schedule-trigger"),
    path("alert-rules/", AlertRuleListCreateView.as_view(), name="alert-rule-list"),
    path("alert-rules/<int:rule_id>/", AlertRuleDetailView.as_view(), name="alert-rule-detail"),
    path("notification-events/", NotificationEventListView.as_view(), name="notification-event-list"),
    path("preferences/workspace/", WorkspaceNotificationPreferenceView.as_view(), name="workspace-notification-preference"),
    path("preferences/me/", UserNotificationPreferenceView.as_view(), name="user-notification-preference"),
]
