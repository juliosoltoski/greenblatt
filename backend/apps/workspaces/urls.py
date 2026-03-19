from django.urls import path

from apps.workspaces.views import WorkspaceDetailView, WorkspaceListView


urlpatterns = [
    path("", WorkspaceListView.as_view(), name="workspace-list"),
    path("<int:workspace_id>/", WorkspaceDetailView.as_view(), name="workspace-detail"),
]
