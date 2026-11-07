from django.contrib import admin

from .models import (
    Asset, AssetCategory, AssetLocation, AssetMaintenance, AssetMovement,
    ContentEntry, ContentRevision, DutyRoster, FinanceTransaction, MediaItem, PrivacyRequest, WorkerLeaveRequest,
)


admin.site.register([
    Asset, AssetCategory, AssetLocation, AssetMaintenance, AssetMovement,
    ContentEntry, ContentRevision, DutyRoster, FinanceTransaction, MediaItem, WorkerLeaveRequest,
])


@admin.register(PrivacyRequest)
class PrivacyRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "request_type", "status", "created_at", "deletion_due_at", "completed_at")
    list_filter = ("request_type", "status")
    readonly_fields = ("user", "request_type", "reason", "created_at", "deletion_due_at")
