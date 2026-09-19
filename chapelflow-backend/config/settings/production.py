from .base import *  # noqa

from django.core.exceptions import ImproperlyConfigured

if not SECRET_KEY or SECRET_KEY in {  # noqa: F405
    DEVELOPMENT_SECRET_KEY,
    LEGACY_DEVELOPMENT_SECRET_KEY,
}:
    raise ImproperlyConfigured(
        "SECRET_KEY must be set to a non-development value in production."
    )

DEBUG = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 hours

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

CORS_ALLOW_ALL_ORIGINS = False
