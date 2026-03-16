from __future__ import annotations

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
import redis


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
