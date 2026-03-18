from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4


_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
_CORRELATION_ID: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_JOB_ID: ContextVar[str | None] = ContextVar("job_id", default=None)
_TASK_ID: ContextVar[str | None] = ContextVar("task_id", default=None)
_WORKSPACE_ID: ContextVar[str | None] = ContextVar("workspace_id", default=None)
_USER_ID: ContextVar[str | None] = ContextVar("user_id", default=None)
_PATH: ContextVar[str | None] = ContextVar("path", default=None)
_METHOD: ContextVar[str | None] = ContextVar("method", default=None)


def generate_request_id() -> str:
    return uuid4().hex


def set_observability_context(
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
    job_id: str | int | None = None,
    task_id: str | None = None,
    workspace_id: str | int | None = None,
    user_id: str | int | None = None,
    path: str | None = None,
    method: str | None = None,
) -> None:
    _REQUEST_ID.set(request_id)
    _CORRELATION_ID.set(correlation_id)
    _JOB_ID.set(str(job_id) if job_id is not None else None)
    _TASK_ID.set(task_id)
    _WORKSPACE_ID.set(str(workspace_id) if workspace_id is not None else None)
    _USER_ID.set(str(user_id) if user_id is not None else None)
    _PATH.set(path)
    _METHOD.set(method)


def clear_observability_context() -> None:
    set_observability_context()


def current_request_id() -> str | None:
    return _REQUEST_ID.get()


def current_correlation_id() -> str | None:
    return _CORRELATION_ID.get()


def current_job_id() -> str | None:
    return _JOB_ID.get()


def current_task_id() -> str | None:
    return _TASK_ID.get()


def current_observability_context() -> dict[str, str]:
    context = {
        "request_id": _REQUEST_ID.get(),
        "correlation_id": _CORRELATION_ID.get(),
        "job_id": _JOB_ID.get(),
        "task_id": _TASK_ID.get(),
        "workspace_id": _WORKSPACE_ID.get(),
        "user_id": _USER_ID.get(),
        "path": _PATH.get(),
        "method": _METHOD.get(),
    }
    return {key: value for key, value in context.items() if value}
