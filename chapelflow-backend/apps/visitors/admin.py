from django.contrib import admin

from .models import Visitor, VisitorFollowUp


class VisitorFollowUpInline(admin.TabularInline):
    model = VisitorFollowUp
    extra = 0


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "branch", "status", "created_at")
    list_filter = ("branch", "status")
    search_fields = ("full_name", "phone_number", "email")
    inlines = [VisitorFollowUpInline]
