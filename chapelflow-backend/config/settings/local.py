"""Self-contained local settings used by the React/Django development command."""
import os

from .development import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / os.environ.get("CHAPELFLOW_LOCAL_DATABASE", "chapelflow-local.sqlite3"),
    }
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
MFA_ENFORCED_ROLES = []
MFA_ENFORCE_ROLE_OBJECTS = False
