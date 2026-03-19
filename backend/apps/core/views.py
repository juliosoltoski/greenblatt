from __future__ import annotations

from django.conf import settings
from django.db import connection
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
import redis
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.metrics import CONTENT_TYPE_LATEST, metrics_content
from apps.core.providers import configured_provider_health_payload
from apps.core.provider_operations import ProviderCacheWarmJobService, ProviderCacheWarmRequest, provider_diagnostics_payload
from apps.core.serializers import ProviderCacheWarmLaunchSerializer
from apps.core.throttling import LaunchRateThrottle
from apps.jobs.presenters import serialize_job
from apps.universes.models import Universe
from apps.workspaces.access import require_workspace_role, resolve_workspace_for_request


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


class ProviderDiagnosticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        probe = str(request.query_params.get("probe", "")).strip().lower() in {"1", "true", "yes", "on"}
        workspace_id = request.query_params.get("workspace_id")
        workspace = resolve_workspace_for_request(request.user, int(workspace_id) if workspace_id else None)
        return Response(provider_diagnostics_payload(workspace=workspace, probe=probe))


class ProviderCacheWarmLaunchView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [LaunchRateThrottle]

    def post(self, request):
        serializer = ProviderCacheWarmLaunchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        require_workspace_role(
            request.user,
            workspace,
            "analyst",
            "You need analyst access or higher to warm provider caches.",
        )
        universe = Universe.objects.filter(workspace=workspace, pk=serializer.validated_data["universe_id"]).first()
        if universe is None:
            return Response({"detail": "The requested universe was not found in this workspace."}, status=status.HTTP_404_NOT_FOUND)

        job = ProviderCacheWarmJobService().launch_cache_warm(
            ProviderCacheWarmRequest(
                workspace=workspace,
                created_by=request.user,
                universe=universe,
                sample_size=serializer.validated_data["sample_size"],
                refresh_cache=serializer.validated_data["refresh_cache"],
                cache_ttl_hours=serializer.validated_data["cache_ttl_hours"],
                provider_name=serializer.validated_data.get("provider_name") or None,
                fallback_provider_name=serializer.validated_data.get("fallback_provider_name") or None,
            )
        )
        response_status = status.HTTP_202_ACCEPTED if job.state == "queued" else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response({"job": serialize_job(job)}, status=response_status)
