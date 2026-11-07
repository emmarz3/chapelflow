from django.contrib import admin

from .models import AttendanceRecord, AttendanceSession, CheckInDevice, VisitorAttendance


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ["label", "venue", "branch", "is_open", "opened_at"]
    list_filter = ["branch", "is_open"]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ["member", "session", "method", "checked_in_at"]
    list_filter = ["method"]
    readonly_fields = ["id", "created_at"]

    def has_add_permission(self, request):
        return False  # records must go through check-in/sync endpoints


admin.site.register(CheckInDevice)
admin.site.register(VisitorAttendance)
