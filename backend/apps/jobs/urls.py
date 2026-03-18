from django.urls import path

from apps.jobs.views import JobDetailView, JobListView, SmokeJobLaunchView


urlpatterns = [
    path("", JobListView.as_view(), name="job-list"),
    path("smoke/", SmokeJobLaunchView.as_view(), name="job-smoke-launch"),
    path("<int:job_id>/", JobDetailView.as_view(), name="job-detail"),
]
