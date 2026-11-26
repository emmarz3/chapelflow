import logging
from time import monotonic


logger = logging.getLogger("chapelflow.performance")


class SlowRequestMiddleware:
    """Log route templates and latency, excluding paths, query strings, and personal data."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = monotonic()
        response = self.get_response(request)
        duration_ms = round((monotonic() - started) * 1000)
        if duration_ms >= 1500:
            match = getattr(request, "resolver_match", None)
            logger.warning("slow_request method=%s route=%s status=%s duration_ms=%s",
                           request.method, match.view_name if match else "unresolved", response.status_code, duration_ms)
        return response
