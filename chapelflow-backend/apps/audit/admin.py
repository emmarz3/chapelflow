from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "resource_type", "resource_id", "user", "created_at"]
    list_filter = ["action", "resource_type"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    search_fields = ["resource_id", "user__email", "user__matric_no"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # emergency-only, still logged at the DB level
