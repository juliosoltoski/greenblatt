from django.urls import path

from apps.jobs.views import (
    JobCancelView,
    JobDetailView,
    JobEventListView,
    JobListView,
    JobRetryView,
    JobStreamView,
    SmokeJobLaunchView,
)


urlpatterns = [
    path("", JobListView.as_view(), name="job-list"),
    path("smoke/", SmokeJobLaunchView.as_view(), name="job-smoke-launch"),
    path("<int:job_id>/", JobDetailView.as_view(), name="job-detail"),
    path("<int:job_id>/events/", JobEventListView.as_view(), name="job-event-list"),
    path("<int:job_id>/stream/", JobStreamView.as_view(), name="job-stream"),
    path("<int:job_id>/cancel/", JobCancelView.as_view(), name="job-cancel"),
    path("<int:job_id>/retry/", JobRetryView.as_view(), name="job-retry"),
]
