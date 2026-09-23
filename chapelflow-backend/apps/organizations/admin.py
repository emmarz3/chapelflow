from django.contrib import admin

from .models import Branch, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    search_fields = ["name", "slug"]


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "branch_type", "parent", "is_active"]
    list_filter = ["branch_type", "is_active", "organization"]
    search_fields = ["name", "city"]
