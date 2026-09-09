from .base import *  # noqa

import os

# Opt-in local test backend for contributors without the Docker/PostgreSQL
# stack. Production and CI continue using DATABASE_URL from base.py.
if os.environ.get("CHAPELFLOW_TEST_SQLITE") == "1":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "chapelflow-test.sqlite3",
        }
    }

DEBUG = False

# Fast password hashing for tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# MFA enforcement (spec section 18) is exercised deliberately, per-test,
# via @override_settings(MFA_ENFORCED_ROLES=[...]) in tests/accounts/ —
# not left on globally here. Turning it on by default would silently
# require every fixture-created SUPER_ADMIN/CHAPEL_ADMIN/FINANCE_OFFICER
# across the whole suite to also enroll in MFA, which is unrelated to
# what most of those tests are actually verifying.
MFA_ENFORCED_ROLES = []
MFA_ENFORCE_ROLE_OBJECTS = False
