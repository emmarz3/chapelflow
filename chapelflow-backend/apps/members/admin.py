from django.contrib import admin
from django.utils.html import format_html
from rangefilter.filters import NumericRangeFilterBuilder

from .models import Member, MemberQRCode, MembershipHistory, MemberTag, MemberFollowUp, EngagementMetrics


class MemberTagInline(admin.TabularInline):
    model = MemberTag
    extra = 0


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["full_name", "branch", "membership_status", "email", "phone_number"]
    list_filter = ["branch", "membership_status", "gender"]
    search_fields = ["first_name", "last_name", "email", "phone_number"]
    inlines = [MemberTagInline]


@admin.register(MembershipHistory)
class MembershipHistoryAdmin(admin.ModelAdmin):
    list_display = ["member", "previous_status", "new_status", "created_at"]
    readonly_fields = [f.name for f in MembershipHistory._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(MemberQRCode)
class MemberQRCodeAdmin(admin.ModelAdmin):
    list_display = ["member", "is_active", "created_at"]
    readonly_fields = ["token"]


@admin.register(MemberFollowUp)
class MemberFollowUpAdmin(admin.ModelAdmin):
    """
    Phase 11: Admin interface for member follow-ups.
    
    Security:
    - Notes field excluded from list view (privacy)
    - Can filter by branch via member__branch
    - Read-only: member, milestone, scheduled_for (auto-generated)
    - Editable: assigned_to, completed_at, notes
    """
    list_display = [
        "member",
        "get_branch",
        "milestone",
        "assigned_to",
        "scheduled_for",
        "completed_status",
        "reminder_status",
    ]
    list_filter = [
        "milestone",
        "member__branch",
        "assigned_to",
        ("completed_at", admin.EmptyFieldListFilter),
        ("reminder_sent_at", admin.EmptyFieldListFilter),
    ]
    search_fields = [
        "member__first_name",
        "member__last_name",
        "assigned_to__email",
        "notes",
    ]
    readonly_fields = [
        "id",
        "member",
        "milestone",
        "scheduled_for",
        "reminder_sent_at",
        "created_at",
        "updated_at",
    ]
    fields = [
        "id",
        "member",
        "milestone",
        "assigned_to",
        "scheduled_for",
        "completed_at",
        "notes",
        "reminder_sent_at",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "scheduled_for"
    ordering = ["-scheduled_for"]
    
    def get_branch(self, obj):
        """Display member's branch for filtering."""
        return obj.member.branch.name if obj.member and obj.member.branch else "-"
    get_branch.short_description = "Branch"
    get_branch.admin_order_field = "member__branch__name"
    
    def completed_status(self, obj):
        """Visual indicator for completion status."""
        if obj.completed_at:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Completed</span>'
            )
        return format_html(
            '<span style="color: orange;">⏳ Pending</span>'
        )
    completed_status.short_description = "Status"
    
    def reminder_status(self, obj):
        """Visual indicator for reminder status."""
        if obj.reminder_sent_at:
            return format_html(
                '<span style="color: blue;">✉ Sent</span>'
            )
        return format_html(
            '<span style="color: gray;">-</span>'
        )
    reminder_status.short_description = "Reminder"
    
    def has_add_permission(self, request):
        """
        Prevent manual creation via admin.
        Follow-ups are created by signal or API only.
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deletion via admin to preserve audit trail.
        Use completed_at to mark as done instead.
        """
        return False


@admin.register(EngagementMetrics)
class EngagementMetricsAdmin(admin.ModelAdmin):
    """
    Phase 11: Admin interface for engagement metrics.
    
    Security:
    - Read-only (calculated by Celery task)
    - Giving metrics visible but privacy-sensitive
    - Can filter by engagement level
    """
    list_display = [
        "member",
        "get_branch",
        "engagement_score",
        "days_since_last_activity",
        "services_30d",
        "events_30d",
        "volunteer_active",
        "last_calculated_at",
    ]
    list_filter = [
        "member__branch",
        ("engagement_score", NumericRangeFilterBuilder()),
        ("days_since_last_activity", NumericRangeFilterBuilder()),
    ]
    search_fields = [
        "member__first_name",
        "member__last_name",
    ]
    readonly_fields = [f.name for f in EngagementMetrics._meta.fields]
    fieldsets = (
        ("Member", {
            "fields": ("member",)
        }),
        ("Attendance Metrics", {
            "fields": (
                "services_attended_30d",
                "services_attended_90d",
                "last_service_date",
                "attendance_rate_30d",
            )
        }),
        ("Event Participation", {
            "fields": (
                "events_attended_30d",
                "events_attended_90d",
                "last_event_date",
            )
        }),
        ("Volunteering", {
            "fields": (
                "volunteer_assignments_active",
                "volunteer_assignments_completed",
                "last_volunteer_date",
            )
        }),
        ("Giving (Privacy-Sensitive)", {
            "fields": (
                "giving_count_30d",
                "giving_count_90d",
                "last_giving_date",
            ),
            "classes": ("collapse",),  # Collapsed by default for privacy
        }),
        ("Overall Engagement", {
            "fields": (
                "engagement_score",
                "days_since_last_activity",
                "last_calculated_at",
            )
        }),
    )
    date_hierarchy = "last_calculated_at"
    ordering = ["-engagement_score"]
    
    def get_branch(self, obj):
        """Display member's branch for filtering."""
        return obj.member.branch.name if obj.member and obj.member.branch else "-"
    get_branch.short_description = "Branch"
    get_branch.admin_order_field = "member__branch__name"
    
    def services_30d(self, obj):
        """Display 30-day service attendance."""
        return obj.services_attended_30d
    services_30d.short_description = "Services (30d)"
    
    def events_30d(self, obj):
        """Display 30-day event participation."""
        return obj.events_attended_30d
    events_30d.short_description = "Events (30d)"
    
    def volunteer_active(self, obj):
        """Display active volunteer assignments."""
        return obj.volunteer_assignments_active
    volunteer_active.short_description = "Volunteer (Active)"
    
    def has_add_permission(self, request):
        """
        Prevent manual creation.
        Metrics are calculated by Celery task only.
        """
        return False
    
    def has_delete_permission(self, request, obj=None):
        """
        Prevent deletion to preserve historical data.
        Metrics are automatically updated by task.
        """
        return False
