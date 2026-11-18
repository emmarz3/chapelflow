import threading

_audit_local = threading.local()


class AuditContextMiddleware:
    """
    Makes the current request's user/IP/user-agent available to model
    signal handlers so audit log entries can be written without threading
    the request through every service function.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _audit_local.user = getattr(request, "user", None)
        _audit_local.ip_address = self._get_client_ip(request)
        _audit_local.user_agent = request.META.get("HTTP_USER_AGENT", "")
        try:
            response = self.get_response(request)
        finally:
            _audit_local.user = None
            _audit_local.ip_address = None
            _audit_local.user_agent = None
        return response

    @staticmethod
    def _get_client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")


def get_current_audit_context():
    return {
        "user": getattr(_audit_local, "user", None),
        "ip_address": getattr(_audit_local, "ip_address", None),
        "user_agent": getattr(_audit_local, "user_agent", None),
    }
