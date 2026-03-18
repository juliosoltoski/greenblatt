from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from apps.core.context import current_observability_context


class ObservabilityContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = current_observability_context()
        record.request_id = context.get("request_id", "-")
        record.correlation_id = context.get("correlation_id", "-")
        record.job_id = context.get("job_id", "-")
        record.task_id = context.get("task_id", "-")
        record.workspace_id = context.get("workspace_id", "-")
        record.user_id = context.get("user_id", "-")
        record.request_path = context.get("path", "-")
        record.request_method = context.get("method", "-")
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "correlation_id",
            "job_id",
            "task_id",
            "workspace_id",
            "user_id",
            "request_path",
            "request_method",
        ):
            value = getattr(record, key, "-")
            if value and value != "-":
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, sort_keys=True)


def build_logging_config(*, log_level: str, json_logs: bool) -> dict[str, Any]:
    formatter_name = "json" if json_logs else "console"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "observability": {
                "()": "apps.core.logging.ObservabilityContextFilter",
            }
        },
        "formatters": {
            "console": {
                "format": (
                    "%(asctime)s %(levelname)s %(name)s "
                    "request_id=%(request_id)s correlation_id=%(correlation_id)s "
                    "job_id=%(job_id)s task_id=%(task_id)s workspace_id=%(workspace_id)s "
                    "user_id=%(user_id)s %(message)s"
                )
            },
            "json": {
                "()": "apps.core.logging.JsonLogFormatter",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "filters": ["observability"],
                "formatter": formatter_name,
            }
        },
        "root": {
            "handlers": ["console"],
            "level": log_level,
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "celery": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
        },
    }
