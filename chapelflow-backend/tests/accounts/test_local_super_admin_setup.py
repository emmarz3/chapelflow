import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient


User = get_user_model()
LOCAL_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    MFA_ENFORCED_ROLES=[],
    MFA_ENFORCE_ROLE_OBJECTS=False,
    CACHES=LOCAL_CACHE,
)
def test_local_setup_creates_and_signs_in_first_super_admin():
    client = APIClient()
    response = client.post(
        "/api/v1/auth/setup/super-admin/",
        {
            "email": "owner@example.com",
            "first_name": "Emmarz",
            "last_name": "Admin",
            "password": "LongUniquePassword123!",
        },
        format="json",
    )

    assert response.status_code == 201
    assert User.objects.get(email="owner@example.com").role == "SUPER_ADMIN"
    assert response.cookies["chapelflow_access"]["httponly"] is True

    duplicate = APIClient().post(
        "/api/v1/auth/setup/super-admin/",
        {
            "email": "another@example.com",
            "first_name": "Another",
            "last_name": "Admin",
            "password": "AnotherLongPassword123!",
        },
        format="json",
    )
    assert duplicate.status_code == 409
    assert User.objects.filter(role="SUPER_ADMIN").count() == 1


@pytest.mark.django_db
@override_settings(DEBUG=False, CACHES=LOCAL_CACHE)
def test_local_setup_is_unavailable_outside_debug():
    response = APIClient().post(
        "/api/v1/auth/setup/super-admin/",
        {
            "email": "owner@example.com",
            "first_name": "Emmarz",
            "last_name": "Admin",
            "password": "LongUniquePassword123!",
        },
        format="json",
    )

    assert response.status_code == 404
    assert not User.objects.filter(role="SUPER_ADMIN").exists()
