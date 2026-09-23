"""
Operational health endpoints (Phase 1).

Three distinct checks, matching container/orchestrator convention:

  - /health/    -- pure liveness: "is the Django process able to respond
                    at all". No dependency I/O. This is what the
                    Dockerfile HEALTHCHECK and any dumb uptime monitor
                    should hit -- it must stay fast and must not flap
                    just because the database had a slow moment.
  - /liveness/  -- identical to /health/. Some orchestrators (k8s-style
                    conventions) specifically look for this path name;
                    kept as an explicit alias rather than a redirect so
                    it behaves identically under any client.
  - /readiness/ -- "can this instance actually serve real requests right
                    now": checks the database and Redis are reachable,
                    and (best-effort) that the Celery broker is
                    reachable. Meant for load-balancer / orchestrator
                    routing decisions, not for process restart decisions.

None of these require authentication -- orchestrators calling them
don't have (and shouldn't need) a ChapelFlow account. None of them ever
return connection strings, hostnames, ports, credentials, or exception
text -- only a per-component up/down status -- so a probe response can't
leak infrastructure details to anyone who can reach the port.

Known scope limit, stated plainly rather than implied: the Celery check
only proves the broker (Redis) socket is reachable from this process.
It does NOT prove a worker is running, processing tasks, or keeping up
with the queue -- that needs real worker monitoring (Flower, Celery
events, queue-depth alerting), which is out of scope for a synchronous
HTTP health probe and isn't attempted here.
"""
import logging

from django.core.cache import cache
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("chapelflow.security")

CELERY_BROKER_CHECK_TIMEOUT_SECONDS = 2


def _check_database() -> bool:
    try:
        connections[DEFAULT_DB_ALIAS].cursor().execute("SELECT 1")
        return True
    except OperationalError:
        return False


def _check_redis() -> bool:
    try:
        probe_key = "healthcheck:readiness:probe"
        cache.set(probe_key, "1", timeout=5)
        return cache.get(probe_key) == "1"
    except Exception:  # noqa: BLE001 -- any cache backend failure means "down"
        return False


def _check_celery_broker() -> bool:
    try:
        from config.celery import app as celery_app

        conn = celery_app.connection(connect_timeout=CELERY_BROKER_CHECK_TIMEOUT_SECONDS)
        conn.ensure_connection(max_retries=0, timeout=CELERY_BROKER_CHECK_TIMEOUT_SECONDS)
        conn.close()
        return True
    except Exception:  # noqa: BLE001 -- any broker failure means "down"
        return False


class LivenessResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok"])


class ReadinessResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "unavailable"])
    checks = serializers.DictField(child=serializers.BooleanField())


class LivenessView(APIView):
    """GET /health/ and /liveness/ -- process is up, nothing more."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: LivenessResponseSerializer})
    def get(self, request):
        return Response({"status": "ok"}, status=200)


class ReadinessView(APIView):
    """GET /readiness/ -- database, Redis, and Celery-broker reachability."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: ReadinessResponseSerializer, 503: ReadinessResponseSerializer})
    def get(self, request):
        checks = {
            "database": _check_database(),
            "redis": _check_redis(),
            "celery_broker": _check_celery_broker(),
        }
        all_ok = all(checks.values())
        if not all_ok:
            logger.warning("Readiness check failed: %s", checks)
        return Response(
            {"status": "ok" if all_ok else "unavailable", "checks": checks},
            status=200 if all_ok else 503,
        )
