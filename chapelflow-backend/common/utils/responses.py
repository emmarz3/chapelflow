from rest_framework.response import Response


def success_response(data=None, message="OK", status=200):
    return Response({"success": True, "message": message, "data": data}, status=status)


def error_response(message="Request failed.", errors=None, status=400):
    return Response({"success": False, "message": message, "errors": errors or {}}, status=status)
