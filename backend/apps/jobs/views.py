from __future__ import annotations

import json
import time

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.throttling import LaunchRateThrottle, MutationRateThrottle
from apps.jobs.models import JobEvent, JobRun
from apps.jobs.presenters import serialize_job, serialize_job_event
from apps.jobs.serializers import JobEventListSerializer, SmokeJobLaunchSerializer
from apps.jobs.services import JobDispatchError, JobService, SmokeJobRequest
from apps.workspaces.access import accessible_workspace_ids, require_workspace_role, resolve_workspace_for_request


def _job_queryset(user):
    return JobRun.objects.select_related("workspace", "created_by").filter(workspace_id__in=accessible_workspace_ids(user))


def _job_event_queryset(user):
    return JobEvent.objects.select_related("workspace", "job").filter(workspace_id__in=accessible_workspace_ids(user))


def _sse(event: str, payload: dict[str, object | None]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


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


class JobEventListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id: int):
        job = get_object_or_404(_job_queryset(request.user), pk=job_id)
        serializer = JobEventListSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        events = _job_event_queryset(request.user).filter(job=job).order_by("-id")[: serializer.validated_data["limit"]]
        ordered = list(reversed(list(events)))
        return Response(
            {
                "workspace_id": job.workspace_id,
                "job_id": job.id,
                "count": len(ordered),
                "results": [serialize_job_event(event) for event in ordered],
            }
        )


class JobStreamView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id: int):
        job = get_object_or_404(_job_queryset(request.user), pk=job_id)
        user = request.user

        def stream():
            last_event_id = 0
            started_at = time.monotonic()
            yield "retry: 3000\n\n"
            while True:
                current_job = _job_queryset(user).get(pk=job.id)
                if last_event_id == 0:
                    yield _sse("job", serialize_job(current_job))
                pending = list(_job_event_queryset(user).filter(job_id=job.id, id__gt=last_event_id).order_by("id")[:200])
                for event in pending:
                    last_event_id = event.id
                    yield _sse("job_event", serialize_job_event(event))
                yield _sse("job", serialize_job(current_job))
                if current_job.is_terminal or (time.monotonic() - started_at) >= 25:
                    break
                time.sleep(1)

        response = StreamingHttpResponse(stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class JobCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [MutationRateThrottle]

    def post(self, request, job_id: int):
        job = get_object_or_404(_job_queryset(request.user), pk=job_id)
        require_workspace_role(request.user, job.workspace, "analyst", "You need analyst access or higher to cancel jobs.")
        job = JobService().request_cancellation(job, requested_by=request.user)
        return Response(serialize_job(job))


class JobRetryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [LaunchRateThrottle]

    def post(self, request, job_id: int):
        job = get_object_or_404(_job_queryset(request.user), pk=job_id)
        require_workspace_role(request.user, job.workspace, "analyst", "You need analyst access or higher to retry jobs.")
        try:
            retried = JobService().retry_job(job, requested_by=request.user)
        except JobDispatchError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        response_status = status.HTTP_202_ACCEPTED if retried.state == JobRun.State.QUEUED else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(serialize_job(retried), status=response_status)


class SmokeJobLaunchView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [LaunchRateThrottle]

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
