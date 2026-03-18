from __future__ import annotations

from django.conf import settings
from django.db import connection
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
import redis
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.metrics import CONTENT_TYPE_LATEST, metrics_content
from apps.core.providers import configured_provider_health_payload


def _database_health() -> dict[str, object]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return {"ok": True, "service": "database"}
    except Exception as exc:  # pragma: no cover - defensive branch for runtime health
        return {"ok": False, "service": "database", "detail": str(exc)}


def _redis_health() -> dict[str, object]:
    try:
        client = redis.from_url(settings.REDIS_URL)
        client.ping()
        return {"ok": True, "service": "redis"}
    except Exception as exc:  # pragma: no cover - defensive branch for runtime health
        return {"ok": False, "service": "redis", "detail": str(exc)}


def live_health(_request):
    return JsonResponse({"status": "ok", "service": "backend"})


def ready_health(_request):
    checks = [_database_health(), _redis_health()]
    healthy = all(bool(check["ok"]) for check in checks)
    status_code = 200 if healthy else 503
    return JsonResponse(
        {
            "status": "ok" if healthy else "degraded",
            "checks": checks,
        },
        status=status_code,
    )


def api_health(request):
    return ready_health(request)


def metrics_view(_request):
    expected_token = getattr(settings, "METRICS_AUTH_TOKEN", None)
    if expected_token:
        provided_token = _request.headers.get("X-Metrics-Token")
        authorization = _request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            provided_token = authorization.removeprefix("Bearer ").strip()
        if provided_token != expected_token:
            return HttpResponseForbidden("Metrics token is invalid.")
    return HttpResponse(metrics_content(), content_type=CONTENT_TYPE_LATEST)


class ProviderListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        probe = str(request.query_params.get("probe", "")).strip().lower() in {"1", "true", "yes", "on"}
        return Response(configured_provider_health_payload(probe=probe))
