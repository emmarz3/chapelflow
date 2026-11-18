from django.contrib import admin

from .models import GroupMembership


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ["member", "group", "role", "is_active"]
    list_filter = ["role", "is_active"]
