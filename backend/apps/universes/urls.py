from django.urls import path

from apps.universes.views import UniverseDetailView, UniverseListCreateView


urlpatterns = [
    path("", UniverseListCreateView.as_view(), name="universe-list"),
    path("<int:universe_id>/", UniverseDetailView.as_view(), name="universe-detail"),
]
