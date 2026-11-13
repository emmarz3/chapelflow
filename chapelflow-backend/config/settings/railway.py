"""Production settings for Railway's internal deployment health check."""

from .production import *  # noqa: F403

ALLOWED_HOSTS = [*ALLOWED_HOSTS, "healthcheck.railway.app"]  # noqa: F405
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
READINESS_REQUIRE_REDIS = True
