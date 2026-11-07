from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import LoginHistory, MFADevice, Permission, RolePermission, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["matric_no", "email", "full_name", "role", "branch", "is_active", "is_staff"]
    list_filter = ["role", "is_active", "is_staff", "branch"]
    search_fields = ["matric_no", "email", "first_name", "last_name"]
    readonly_fields = ["id", "date_joined", "last_login", "last_login_ip"]
    fieldsets = (
        (None, {"fields": ("id", "email", "matric_no", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone_number")}),
        ("Church", {"fields": ("role", "branch")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "mfa_enabled", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined", "last_login_ip")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "matric_no", "password1", "password2", "role")}),
    )


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    search_fields = ["code"]


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ["legacy_role_code", "role_obj", "permission"]
    list_filter = ["legacy_role_code", "role_obj"]


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ["user", "ip_address", "successful", "created_at"]
    list_filter = ["successful"]
    readonly_fields = [f.name for f in LoginHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MFADevice)
class MFADeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "confirmed", "created_at"]
