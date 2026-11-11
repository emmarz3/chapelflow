"""Production settings for the Vercel frontend and API on a shared origin."""
from django.core.exceptions import ImproperlyConfigured

from .production import *  # noqa: F403

if (
    not env("DATABASE_URL", default="")
    or DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql"
):
    raise ImproperlyConfigured("Set DATABASE_URL to the ChapelFlow PostgreSQL database on Vercel.")

DATABASES["default"].setdefault("OPTIONS", {}).setdefault("sslmode", "require")
STATIC_URL = "/static/"

deployment_host = env("VERCEL_URL", default="")
production_host = env("VERCEL_PROJECT_PRODUCTION_URL", default="")
branch_host = env("VERCEL_BRANCH_URL", default="")
for host in dict.fromkeys(filter(None, (deployment_host, production_host, branch_host))):
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

canonical_host = deployment_host
if env("VERCEL_ENV", default="") == "production":
    canonical_host = production_host or deployment_host
canonical_origin = f"https://{canonical_host}" if canonical_host else PUBLIC_BACKEND_URL
PUBLIC_BACKEND_URL = env("PUBLIC_BACKEND_URL", default=canonical_origin).rstrip("/")
FRONTEND_URL = env("FRONTEND_URL", default=PUBLIC_BACKEND_URL).rstrip("/")

# Request-triggered jobs run inline unless a separate Celery worker is active.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=True)
