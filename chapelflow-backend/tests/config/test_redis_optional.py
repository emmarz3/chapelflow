from config.settings.base import _redis_settings


def test_missing_redis_uses_in_memory_cache_and_celery_broker():
    settings = _redis_settings(None)

    assert settings["CELERY_BROKER_URL"] == "memory://"
    assert settings["CELERY_TASK_ALWAYS_EAGER"] is True
    assert (
        settings["CACHES"]["default"]["BACKEND"]
        == "django.core.cache.backends.locmem.LocMemCache"
    )


def test_configured_redis_keeps_redis_cache_and_broker():
    redis_url = "redis://cache.example.test:6379/0"
    settings = _redis_settings(redis_url)

    assert settings["CELERY_BROKER_URL"] == redis_url
    assert settings["CACHES"]["default"]["BACKEND"] == "django_redis.cache.RedisCache"
    assert settings["CACHES"]["default"]["LOCATION"] == redis_url
    assert settings["CACHES"]["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] is True
    assert settings["CACHES"]["default"]["OPTIONS"]["SOCKET_CONNECT_TIMEOUT"] == 2
    assert settings["CACHES"]["default"]["OPTIONS"]["SOCKET_TIMEOUT"] == 2
    assert "CELERY_TASK_ALWAYS_EAGER" not in settings
