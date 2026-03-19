from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import LoginRateThrottle
from apps.accounts.serializers import CurrentUserUpdateSerializer, LoginSerializer, serialize_user
from apps.core.plans import plan_catalog_payload, workspace_plan_payload, workspace_usage_payload
from apps.jobs.models import JobRun
from apps.workspaces.access import resolve_workspace_for_request
from apps.workspaces.models import Workspace


User = get_user_model()


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfTokenView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(serialize_user(request.user))

    def patch(self, request):
        serializer = CurrentUserUpdateSerializer(instance=request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(serialize_user(user))


class LoginView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response({"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(serialize_user(user))


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "Logged out."})


class AccountSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace_id = request.query_params.get("workspace_id")
        workspace = resolve_workspace_for_request(request.user, int(workspace_id) if workspace_id else None)
        return Response(
            {
                "user": serialize_user(request.user),
                "workspace": {
                    **workspace_usage_payload(workspace),
                    "summary": {
                        "id": workspace.id,
                        "name": workspace.name,
                        "slug": workspace.slug,
                        "plan_type": workspace.plan_type,
                        "timezone": workspace.timezone,
                        "owner_id": workspace.owner_id,
                    },
                },
                "plan": workspace_plan_payload(workspace),
                "plan_catalog": plan_catalog_payload(),
                "auth_capabilities": {
                    "session_auth_enabled": True,
                    "social_login_enabled": bool(getattr(settings, "SOCIAL_LOGIN_ENABLED", False)),
                    "billing_enabled": bool(getattr(settings, "BILLING_ENABLED", False)),
                },
                "notices": {
                    "research_only": "This product is positioned for research workflow support, not live trade execution.",
                    "provider_usage": "Provider payloads and quotas can differ by vendor. Review vendor terms before external or commercial use.",
                    "billing": "Plan labels and quota summaries are informational groundwork. Commercial billing is not enabled yet.",
                    "support_contact": getattr(settings, "SUPPORT_CONTACT_EMAIL", "support@example.test"),
                },
                "support_overview": _support_overview() if request.user.is_staff else None,
            }
        )


def _support_overview() -> dict[str, object]:
    from django.utils import timezone

    window_start = timezone.now() - timedelta(days=7)
    recent_failures = (
        JobRun.objects.select_related("workspace")
        .filter(state__in=[JobRun.State.FAILED, JobRun.State.PARTIAL_FAILED])
        .order_by("-updated_at")[:5]
    )
    return {
        "user_count": User.objects.count(),
        "workspace_count": Workspace.objects.count(),
        "active_job_count": JobRun.objects.filter(state__in=[JobRun.State.QUEUED, JobRun.State.RUNNING]).count(),
        "failed_job_count_7d": JobRun.objects.filter(
            state__in=[JobRun.State.FAILED, JobRun.State.PARTIAL_FAILED],
            updated_at__gte=window_start,
        ).count(),
        "provider_failure_count_7d": JobRun.objects.filter(
            error_code__in=["provider_failure", "provider_build_failed"],
            updated_at__gte=window_start,
        ).count(),
        "recent_failures": [
            {
                "job_id": job.id,
                "workspace_name": job.workspace.name,
                "job_type": job.job_type,
                "error_code": job.error_code or None,
                "error_message": job.error_message or None,
                "updated_at": job.updated_at.isoformat(),
            }
            for job in recent_failures
        ],
    }
