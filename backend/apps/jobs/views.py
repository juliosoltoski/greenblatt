from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.jobs.models import JobRun
from apps.jobs.presenters import serialize_job
from apps.jobs.serializers import SmokeJobLaunchSerializer
from apps.jobs.services import JobService, SmokeJobRequest
from apps.workspaces.access import accessible_workspace_ids, require_workspace_role, resolve_workspace_for_request


def _job_queryset(user):
    return JobRun.objects.select_related("workspace", "created_by").filter(workspace_id__in=accessible_workspace_ids(user))


class JobListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        workspace_id = request.query_params.get("workspace_id")
        workspace = resolve_workspace_for_request(request.user, int(workspace_id) if workspace_id else None)
        raw_limit = request.query_params.get("limit", "20")
        try:
            limit = min(100, max(1, int(raw_limit)))
        except ValueError:
            limit = 20
        jobs = _job_queryset(request.user).filter(workspace=workspace)[:limit]
        return Response({"workspace_id": workspace.id, "results": [serialize_job(job) for job in jobs]})


class JobDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id: int):
        job = get_object_or_404(_job_queryset(request.user), pk=job_id)
        return Response(serialize_job(job))


class SmokeJobLaunchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SmokeJobLaunchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        workspace = resolve_workspace_for_request(request.user, serializer.validated_data.get("workspace_id"))
        require_workspace_role(
            request.user,
            workspace,
            "analyst",
            "You need analyst access or higher to launch jobs.",
        )

        job = JobService().launch_smoke_job(
            SmokeJobRequest(
                workspace=workspace,
                created_by=request.user,
                step_count=serializer.validated_data["step_count"],
                step_delay_ms=serializer.validated_data["step_delay_ms"],
                failure_mode=serializer.validated_data["failure_mode"],
            )
        )
        response_status = status.HTTP_202_ACCEPTED if job.state == JobRun.State.QUEUED else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(serialize_job(job), status=response_status)
