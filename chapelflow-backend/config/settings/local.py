"""Self-contained local settings used by the React/Django development command."""
import os

from .development import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / os.environ.get("CHAPELFLOW_LOCAL_DATABASE", "chapelflow-local.sqlite3"),
    }
}
# Keep uploads on this machine during local development, even when a shared
# environment file contains production storage settings.
STORAGE_PROVIDER = "local"
PUBLIC_BACKEND_URL = "http://127.0.0.1:8000"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# Local tasks execute synchronously, so an in-memory broker keeps health
# checks honest without requiring a separate Redis/Celery service.
CELERY_BROKER_URL = "memory://"
MFA_ENFORCED_ROLES = []
MFA_ENFORCE_ROLE_OBJECTS = False
