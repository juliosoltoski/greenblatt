from django.contrib import admin
from django.urls import path

from apps.core.views import api_health, live_health, ready_health


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/live/", live_health, name="health-live"),
    path("health/ready/", ready_health, name="health-ready"),
    path("api/health/", api_health, name="api-health"),
]
