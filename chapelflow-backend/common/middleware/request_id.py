import logging
import threading
import uuid

_local = threading.local()


class RequestIDMiddleware:
    """Attaches a unique request ID to every request for traceable logging."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.request_id = request_id
        _local.request_id = request_id
        try:
            response = self.get_response(request)
        finally:
            _local.request_id = None
        response["X-Request-ID"] = request_id
        return response


class RequestIDLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(_local, "request_id", None) or "-"
        return True
