from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from common.health import LivenessView, ReadinessView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Operational health endpoints (Phase 1) -- unauthenticated, no
    # dependency I/O leaked in the response. See common/health.py.
    path("health/", LivenessView.as_view(), name="health"),
    path("liveness/", LivenessView.as_view(), name="liveness"),
    path("readiness/", ReadinessView.as_view(), name="readiness"),

    # OpenAPI / Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),

    # v1 API
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.organizations.urls")),
    path("api/v1/", include("apps.university.urls")),
    path("api/v1/", include("apps.members.urls")),
    path("api/v1/visitors/", include("apps.visitors.urls")),
    path("api/v1/", include("apps.households.urls")),
    path("api/v1/", include("apps.ministries.urls")),
    path("api/v1/", include("apps.groups.urls")),
    path("api/v1/", include("apps.events.urls")),
    path("api/v1/attendance/", include("apps.attendance.urls")),
    path("api/v1/", include("apps.finance.urls")),
    path("api/v1/communications/", include("apps.communications.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
    path("api/v1/prayer/", include("apps.prayer.urls")),
    path("api/v1/pastoral/", include("apps.pastoral.urls")),
    path("api/v1/volunteers/", include("apps.volunteers.urls")),
    path("api/v1/reports/", include("apps.reports.urls")),
    path("api/v1/dashboard/", include("apps.dashboard.urls")),
    path("api/v1/uploads/", include("apps.uploads.urls")),
    path("api/v1/audit/", include("apps.audit.urls")),
    path("api/v1/", include("apps.operations.urls")),
    path("api/v1/social/", include("apps.social.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
