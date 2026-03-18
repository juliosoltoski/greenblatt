from django.urls import path

from apps.screens.views import ScreenDetailView, ScreenExclusionListView, ScreenExportDownloadView, ScreenJsonExportView, ScreenListCreateView, ScreenResultRowListView


urlpatterns = [
    path("", ScreenListCreateView.as_view(), name="screen-list-create"),
    path("<int:screen_run_id>/", ScreenDetailView.as_view(), name="screen-detail"),
    path("<int:screen_run_id>/results/", ScreenResultRowListView.as_view(), name="screen-results"),
    path("<int:screen_run_id>/exclusions/", ScreenExclusionListView.as_view(), name="screen-exclusions"),
    path("<int:screen_run_id>/export/", ScreenExportDownloadView.as_view(), name="screen-export"),
    path("<int:screen_run_id>/export/json/", ScreenJsonExportView.as_view(), name="screen-export-json"),
]
