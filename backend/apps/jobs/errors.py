from __future__ import annotations

from collections.abc import Callable

from greenblatt.providers.errors import is_provider_exception


class ProviderFailureError(RuntimeError):
    error_code = "provider_failure"

    def __init__(self, message: str, *, provider_name: str, workflow: str) -> None:
        super().__init__(message)
        self.provider_name = provider_name
        self.workflow = workflow


class ProviderBuildError(ProviderFailureError):
    error_code = "provider_build_failed"


def provider_name_from_factory(provider_factory: Callable[..., object]) -> str:
    explicit_name = getattr(provider_factory, "provider_name", None)
    if isinstance(explicit_name, str) and explicit_name.strip():
        return explicit_name.strip()
    raw_name = getattr(provider_factory, "__name__", None)
    if not isinstance(raw_name, str) or not raw_name.strip() or raw_name == "MagicMock":
        mock_name = getattr(provider_factory, "_mock_name", None)
        if isinstance(mock_name, str) and mock_name.strip():
            raw_name = mock_name
        else:
            raw_name = provider_factory.__class__.__name__
    normalized = raw_name.replace("build_", "").replace("_provider", "").strip("_")
    return normalized or "unknown"


def provider_failure_metadata(exc: BaseException) -> dict[str, str] | None:
    provider_name = getattr(exc, "provider_name", None)
    workflow = getattr(exc, "workflow", None)
    if not provider_name or not workflow:
        return None
    return {
        "provider_name": str(provider_name),
        "workflow": str(workflow),
        "exception_type": exc.__class__.__name__,
    }


def wrap_provider_runtime_error(
    exc: BaseException,
    *,
    provider_name: str,
    workflow: str,
) -> ProviderFailureError | None:
    if isinstance(exc, ProviderFailureError):
        return exc

    if not is_provider_exception(exc):
        return None

    return ProviderFailureError(
        f"{workflow.title()} execution failed while reading market data from provider '{provider_name}': {exc}",
        provider_name=provider_name,
        workflow=workflow,
    )
