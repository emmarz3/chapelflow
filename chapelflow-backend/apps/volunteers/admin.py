"""
Phase 9: Django Admin configuration for volunteer management.

Provides staff interface for:
- Volunteer profiles with member relationship
- Volunteer availability windows
- Volunteer assignments with full lifecycle
- Service hour tracking and history
"""
from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html

from .models import VolunteerAssignment, VolunteerAvailability, VolunteerProfile


class VolunteerAvailabilityInline(admin.TabularInline):
    """Inline availability windows for volunteer profile admin."""
    model = VolunteerAvailability
    extra = 0
    fields = ["weekday", "start_time", "end_time", "is_available"]
    ordering = ["weekday", "start_time"]


class VolunteerAssignmentInline(admin.TabularInline):
    """Inline assignments for volunteer profile admin."""
    model = VolunteerAssignment
    extra = 0
    fields = ["event_schedule", "group", "role", "status", "hours_logged"]
    readonly_fields = ["status", "hours_logged"]
    ordering = ["-created_at"]
    
    def has_add_permission(self, request, obj=None):
        """Prevent creating assignments via inline (use main form for conflict checks)."""
        return False


@admin.register(VolunteerProfile)
class VolunteerProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for volunteer profiles.
    
    Features:
    - Inline availability windows
    - Inline assignment history
    - Total service hours calculation
    - Status management
    - Member relationship display
    """
    list_display = [
        "id",
        "member_name",
        "branch",
        "status",
        "is_active",
        "total_service_hours",
        "assignment_count",
        "created_at",
    ]
    list_filter = ["status", "is_active", "member__branch", "created_at"]
    search_fields = [
        "member__first_name",
        "member__last_name",
        "member__email",
        "member__phone",
    ]
    readonly_fields = ["id", "created_at", "total_service_hours", "assignment_count"]
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("id", "member", "status", "is_active")
        }),
        ("Skills & Notes", {
            "fields": ("skills", "availability_notes")
        }),
        ("Statistics", {
            "fields": ("total_service_hours", "assignment_count", "created_at"),
            "classes": ("collapse",),
        }),
    )
    
    inlines = [VolunteerAvailabilityInline, VolunteerAssignmentInline]
    
    def member_name(self, obj):
        """Display member's full name."""
        return str(obj.member)
    member_name.short_description = "Member"
    member_name.admin_order_field = "member__first_name"
    
    def branch(self, obj):
        """Display member's branch."""
        return obj.member.branch.name if obj.member and obj.member.branch else "-"
    branch.short_description = "Branch"
    branch.admin_order_field = "member__branch__name"
    
    def total_service_hours(self, obj):
        """Calculate total service hours from completed assignments."""
        total = VolunteerAssignment.objects.filter(
            volunteer=obj,
            status="COMPLETED"
        ).aggregate(total=Sum("hours_logged"))["total"]
        return f"{total or 0:.2f} hours"
    total_service_hours.short_description = "Total Service Hours"
    
    def assignment_count(self, obj):
        """Count total assignments (all statuses)."""
        return obj.assignments.count()
    assignment_count.short_description = "Assignments"


@admin.register(VolunteerAvailability)
class VolunteerAvailabilityAdmin(admin.ModelAdmin):
    """
    Admin interface for volunteer availability windows.
    
    Features:
    - Grouped by volunteer and weekday
    - Available vs unavailable window display
    - Time range validation
    """
    list_display = [
        "id",
        "volunteer",
        "weekday_display",
        "time_range",
        "availability_type",
        "created_at",
    ]
    list_filter = ["weekday", "is_available", "created_at"]
    search_fields = [
        "volunteer__member__first_name",
        "volunteer__member__last_name",
    ]
    readonly_fields = ["id", "created_at"]
    
    fieldsets = (
        ("Volunteer", {
            "fields": ("volunteer",)
        }),
        ("Time Window", {
            "fields": ("weekday", "start_time", "end_time", "is_available")
        }),
        ("Metadata", {
            "fields": ("id", "created_at"),
            "classes": ("collapse",),
        }),
    )
    
    def weekday_display(self, obj):
        """Display weekday name."""
        return obj.get_weekday_display()
    weekday_display.short_description = "Day"
    weekday_display.admin_order_field = "weekday"
    
    def time_range(self, obj):
        """Display time range."""
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
    time_range.short_description = "Time"
    
    def availability_type(self, obj):
        """Display availability type with color coding."""
        if obj.is_available:
            return format_html('<span style="color: green;">✓ Available</span>')
        else:
            return format_html('<span style="color: red;">✗ Unavailable</span>')
    availability_type.short_description = "Type"


@admin.register(VolunteerAssignment)
class VolunteerAssignmentAdmin(admin.ModelAdmin):
    """
    Admin interface for volunteer assignments.
    
    Features:
    - Lifecycle status display with colors
    - Service hour tracking
    - Event and group relationships
    - Timeline timestamps
    - Historical data protection
    
    Security:
    - Completed assignments have protected fields (readonly)
    - Status changes should go through services (not direct admin edits)
    """
    list_display = [
        "id",
        "volunteer",
        "role",
        "status_display",
        "event_display",
        "group_display",
        "hours_display",
        "created_at",
    ]
    list_filter = [
        "status",
        "role",
        "volunteer__member__branch",
        "created_at",
        "completed_at",
    ]
    search_fields = [
        "volunteer__member__first_name",
        "volunteer__member__last_name",
        "event_schedule__event__title",
        "group__name",
    ]
    readonly_fields = [
        "id",
        "confirmed",
        "responded_at",
        "completed_at",
        "reminder_sent_at",
        "created_at",
    ]
    
    fieldsets = (
        ("Assignment", {
            "fields": ("volunteer", "event_schedule", "group", "role")
        }),
        ("Status", {
            "fields": ("status", "confirmed", "notes")
        }),
        ("Service Hours", {
            "fields": ("hours_logged",),
            "description": "Hours are only set when assignment is completed.",
        }),
        ("Timeline", {
            "fields": (
                "created_at",
                "responded_at",
                "completed_at",
                "reminder_sent_at",
            ),
            "classes": ("collapse",),
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """
        Protect historical data for completed assignments.
        
        Once completed, most fields become readonly to preserve service history.
        """
        readonly = list(self.readonly_fields)
        
        if obj and obj.status == "COMPLETED":
            # Completed assignments are historical - protect critical fields
            readonly.extend([
                "volunteer",
                "event_schedule",
                "group",
                "role",
                "status",
                "hours_logged",
            ])
        
        return readonly
    
    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            "PENDING": "orange",
            "CONFIRMED": "blue",
            "DECLINED": "gray",
            "COMPLETED": "green",
            "CANCELLED": "red",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = "Status"
    status_display.admin_order_field = "status"
    
    def event_display(self, obj):
        """Display event name if exists."""
        if obj.event_schedule and obj.event_schedule.event:
            return obj.event_schedule.event.title
        return "-"
    event_display.short_description = "Event"
    
    def group_display(self, obj):
        """Display group name if exists."""
        return obj.group.name if obj.group else "-"
    group_display.short_description = "Group"
    
    def hours_display(self, obj):
        """Display service hours with styling."""
        if obj.hours_logged:
            return format_html(
                '<span style="font-weight: bold;">{:.2f}h</span>',
                obj.hours_logged
            )
        return "-"
    hours_display.short_description = "Hours"
    hours_display.admin_order_field = "hours_logged"
