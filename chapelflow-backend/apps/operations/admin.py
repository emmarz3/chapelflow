from django.contrib import admin

from .models import (
    Asset, AssetCategory, AssetLocation, AssetMaintenance, AssetMovement,
    ContentEntry, ContentRevision, DutyRoster, FinanceTransaction, MediaItem, PrivacyRequest, WorkerLeaveRequest,
)


admin.site.register([
    Asset, AssetCategory, AssetLocation, AssetMaintenance, AssetMovement,
    ContentEntry, ContentRevision, DutyRoster, FinanceTransaction, MediaItem, PrivacyRequest, WorkerLeaveRequest,
])
