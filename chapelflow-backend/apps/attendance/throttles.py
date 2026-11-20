"""Independent student and network limits for short attendance codes."""
from rest_framework.throttling import SimpleRateThrottle


class AttendanceCodeUserThrottle(SimpleRateThrottle):
    scope = "attendance_code_user"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": str(request.user.pk)}


class AttendanceCodeIPThrottle(SimpleRateThrottle):
    scope = "attendance_code_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
