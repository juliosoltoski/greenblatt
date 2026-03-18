from __future__ import annotations

import time

from apps.core.context import clear_observability_context, generate_request_id, set_observability_context
from apps.core.metrics import record_http_request


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = (
            request.headers.get("X-Request-ID")
            or request.META.get("HTTP_X_REQUEST_ID")
            or generate_request_id()
        )
        correlation_id = request.headers.get("X-Correlation-ID") or request_id
        workspace_id = request.GET.get("workspace_id") or request.POST.get("workspace_id")
        user = getattr(request, "user", None)
        user_id = user.pk if getattr(user, "is_authenticated", False) else None

        request.request_id = request_id
        request.correlation_id = correlation_id
        started_at = time.perf_counter()
        set_observability_context(
            request_id=request_id,
            correlation_id=correlation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            path=request.path,
            method=request.method,
        )

        status_code = 500
        response = None
        try:
            response = self.get_response(request)
            status_code = response.status_code
            response["X-Request-ID"] = request_id
            return response
        finally:
            route = request.resolver_match.route if getattr(request, "resolver_match", None) else request.path
            duration_seconds = time.perf_counter() - started_at
            record_http_request(
                method=request.method,
                route=route or request.path,
                status_code=status_code,
                duration_seconds=duration_seconds,
            )
            clear_observability_context()
