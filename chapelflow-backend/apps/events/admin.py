from django.contrib import admin

from .models import Event, EventRegistration, EventReminder, EventSchedule, EventType, Location


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "branch", "start_time", "frequency"]
    list_filter = ["branch", "event_type", "frequency"]
    search_fields = ["title"]


admin.site.register(EventType)
admin.site.register(Location)
admin.site.register(EventSchedule)
admin.site.register(EventRegistration)
admin.site.register(EventReminder)
