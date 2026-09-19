"""Browser-safe JWT authentication for the React client.

API clients can continue to use ``Authorization: Bearer``. Browsers receive
short-lived access tokens and rotating refresh tokens only as HttpOnly cookies,
so the SPA never needs to persist credentials in web storage.
"""
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """Authenticate a bearer header first, then fall back to the access cookie."""

    cookie_name = "chapelflow_access"
    csrf_cookie_name = "chapelflow_csrf"
    csrf_header_name = "HTTP_X_CHAPELFLOW_CSRF"

    password_change_paths = {
        "/api/v1/auth/change-password/",
        "/api/v1/auth/logout/",
        "/api/v1/auth/me/",
    }

    def _enforce_required_password_change(self, request, result):
        if result is None:
            return None
        user, _ = result
        if user.password_change_required and request.path not in self.password_change_paths:
            raise AuthenticationFailed("You must change your temporary password before continuing.")
        return result

    def authenticate(self, request):
        header_result = super().authenticate(request)
        if header_result is not None:
            return self._enforce_required_password_change(request, header_result)

        raw_token = request.COOKIES.get(self.cookie_name)
        if not raw_token:
            return None
        if request.method not in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            cookie_token = request.COOKIES.get(self.csrf_cookie_name, "")
            header_token = request.META.get(self.csrf_header_name, "")
            if not cookie_token or not header_token or cookie_token != header_token:
                raise AuthenticationFailed("CSRF validation failed.")
        validated_token = self.get_validated_token(raw_token)
        return self._enforce_required_password_change(
            request, (self.get_user(validated_token), validated_token)
        )
