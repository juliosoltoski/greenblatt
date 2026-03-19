from django.contrib import admin
from django.urls import include, path

from apps.collaboration.views import SharedResourceView
from apps.core.views import (
    ProviderCacheWarmLaunchView,
    ProviderDiagnosticsView,
    ProviderListView,
    api_health,
    live_health,
    metrics_view,
    ready_health,
)
from apps.universes.views import UniverseProfileListView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/automation/", include("apps.automation.urls")),
    path("api/v1/backtests/", include("apps.backtests.urls")),
    path("api/v1/collaboration/", include("apps.collaboration.urls")),
    path("api/v1/jobs/", include("apps.jobs.urls")),
    path("api/v1/providers/diagnostics/", ProviderDiagnosticsView.as_view(), name="provider-diagnostics"),
    path("api/v1/providers/cache-warm/", ProviderCacheWarmLaunchView.as_view(), name="provider-cache-warm"),
    path("api/v1/providers/", ProviderListView.as_view(), name="provider-list"),
    path("api/v1/screens/", include("apps.screens.urls")),
    path("api/v1/strategy-templates/", include("apps.strategy_templates.urls")),
    path("api/v1/universe-profiles/", UniverseProfileListView.as_view(), name="universe-profile-list"),
    path("api/v1/universes/", include("apps.universes.urls")),
    path("api/v1/workspaces/", include("apps.workspaces.urls")),
    path("api/v1/shared/<str:token>/", SharedResourceView.as_view(), name="shared-resource"),
    path("health/live/", live_health, name="health-live"),
    path("health/ready/", ready_health, name="health-ready"),
    path("metrics/", metrics_view, name="metrics"),
    path("api/health/", api_health, name="api-health"),
]
