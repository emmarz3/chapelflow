from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceRecordViewSet, AttendanceScanAttemptViewSet, AttendanceSessionViewSet, CheckInDeviceViewSet,
    KioskCheckInView, ManualCheckInView, OfflineSyncView, QRCheckInView,
    MemberAttendanceHistoryView, MemberAttendancePassView, MemberIdentityPassView,
    StudentUsherScanView, UsherCheckpointTokenView,
    VisitorAttendanceViewSet,
)

router = DefaultRouter()
router.register("sessions", AttendanceSessionViewSet, basename="attendance-session")
router.register("records", AttendanceRecordViewSet, basename="attendance-record")
router.register("scan-attempts", AttendanceScanAttemptViewSet, basename="attendance-scan-attempt")
router.register("devices", CheckInDeviceViewSet, basename="attendance-device")
router.register("visitors", VisitorAttendanceViewSet, basename="attendance-visitor")

urlpatterns = [
    path("qr-check-in/", QRCheckInView.as_view(), name="attendance-qr-check-in"),
    path("check-in/", KioskCheckInView.as_view(), name="attendance-kiosk-check-in"),
    path("manual/", ManualCheckInView.as_view(), name="attendance-manual-check-in"),
    path("sync/", OfflineSyncView.as_view(), name="attendance-sync"),
    path("pass/", MemberAttendancePassView.as_view(), name="attendance-pass"),
    path("identity-pass/", MemberIdentityPassView.as_view(), name="attendance-identity-pass"),
    path("history/me/", MemberAttendanceHistoryView.as_view(), name="attendance-history-me"),
    path("checkpoint/token/", UsherCheckpointTokenView.as_view(), name="attendance-checkpoint-token"),
    path("student-scan/", StudentUsherScanView.as_view(), name="attendance-student-scan"),
] + router.urls
