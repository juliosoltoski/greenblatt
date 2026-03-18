from __future__ import annotations

from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle

from apps.core.metrics import record_api_throttle_rejection


class MethodScopedThrottleMixin:
    throttle_classes_by_method: dict[str, list[type]] = {}

    def get_throttles(self):
        if getattr(self, "request", None) is None:
            return super().get_throttles()
        classes = self.throttle_classes_by_method.get(self.request.method.upper())
        if classes is None:
            return super().get_throttles()
        return [throttle_class() for throttle_class in classes]


class InstrumentedThrottleMixin:
    scope = "default"

    def throttle_failure(self):
        record_api_throttle_rejection(self.scope)
        return super().throttle_failure()


class BurstRateThrottle(InstrumentedThrottleMixin, UserRateThrottle):
    scope = "burst"


class SustainedRateThrottle(InstrumentedThrottleMixin, AnonRateThrottle):
    scope = "anon"


class LoginRateThrottle(InstrumentedThrottleMixin, ScopedRateThrottle):
    scope = "login"


class LaunchRateThrottle(InstrumentedThrottleMixin, ScopedRateThrottle):
    scope = "launch"


class ExportRateThrottle(InstrumentedThrottleMixin, ScopedRateThrottle):
    scope = "export"
