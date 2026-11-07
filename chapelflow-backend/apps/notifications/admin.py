from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "channel", "recipient", "status", "created_at"]
    list_filter = ["channel", "status"]
