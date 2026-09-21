from unittest.mock import patch

import pytest


@pytest.mark.django_db
class TestHealthEndpoints:
    def test_health_returns_ok_without_authentication(self, api_client):
        response = api_client.get("/health/")
        assert response.status_code == 200
        assert response.data["status"] == "ok"

    def test_liveness_returns_ok_without_authentication(self, api_client):
        response = api_client.get("/liveness/")
        assert response.status_code == 200
        assert response.data["status"] == "ok"

    def test_liveness_does_not_touch_the_database(self, api_client):
        """Liveness must stay meaningful even when the DB is down -- it must not query it at all."""
        with patch("django.db.backends.utils.CursorWrapper.execute", side_effect=AssertionError("DB was queried")):
            response = api_client.get("/liveness/")
        assert response.status_code == 200

    def test_readiness_ok_when_database_and_redis_and_broker_are_up(self, api_client):
        with patch("common.health._check_celery_broker", return_value=True):
            response = api_client.get("/readiness/")
        assert response.status_code == 200
        assert response.data["status"] == "ok"
        assert response.data["checks"] == {"database": True, "redis": True, "celery_broker": True}

    def test_readiness_returns_503_when_redis_is_down(self, api_client):
        with patch("common.health._check_redis", return_value=False), \
             patch("common.health._check_celery_broker", return_value=True):
            response = api_client.get("/readiness/")
        assert response.status_code == 503
        assert response.data["status"] == "unavailable"
        assert response.data["checks"]["redis"] is False

    def test_readiness_returns_503_when_database_is_down(self, api_client):
        with patch("common.health._check_database", return_value=False), \
             patch("common.health._check_celery_broker", return_value=True):
            response = api_client.get("/readiness/")
        assert response.status_code == 503
        assert response.data["checks"]["database"] is False

    def test_readiness_never_leaks_connection_details_on_failure(self, api_client):
        """Rule 3 / Phase 1: health endpoints must not leak secrets or infra details, even when failing."""
        with patch("common.health._check_database", return_value=False), \
             patch("common.health._check_redis", return_value=False), \
             patch("common.health._check_celery_broker", return_value=False):
            response = api_client.get("/readiness/")
        body = str(response.data)
        for leaky in ("postgres://", "redis://", "PASSWORD", "SECRET", "@localhost"):
            assert leaky not in body
