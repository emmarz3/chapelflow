from django.contrib import admin

from .models import Group


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "group_type", "branch", "leader", "is_active"]
    list_filter = ["group_type", "branch", "is_active"]
    search_fields = ["name"]
