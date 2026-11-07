import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("chapelflow.security")


def chapelflow_exception_handler(exc, context):
    """
    Wraps every DRF error response in the ChapelFlow standard envelope and
    ensures no internal details (tracebacks, SQL, secrets) ever leak to clients.
    """
    if isinstance(exc, Http404):
        exc = drf_exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = drf_exceptions.PermissionDenied()

    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception -> generic 500, never leak internals.
        logger.exception("Unhandled exception", exc_info=exc)
        return Response(
            {
                "success": False,
                "message": "An unexpected error occurred. Please try again later.",
                "errors": {},
            },
            status=500,
        )

    if isinstance(response.data, dict) and "detail" in response.data and len(response.data) == 1:
        message = str(response.data["detail"])
        errors = {}
    else:
        message = "Validation failed." if response.status_code == 400 else "Request failed."
        errors = response.data if isinstance(response.data, dict) else {"non_field_errors": response.data}

    response.data = {
        "success": False,
        "message": message,
        "errors": errors,
    }
    return response
