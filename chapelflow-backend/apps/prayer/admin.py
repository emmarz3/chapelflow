from django.contrib import admin
from django.utils.html import format_html

from .models import PrayerNote, PrayerRequest


class PrayerNoteInline(admin.TabularInline):
    """
    Phase 13: Inline prayer notes with append-only enforcement.
    
    Security:
    - Read-only after creation (append-only)
    - Author auto-set, cannot be changed
    """
    model = PrayerNote
    extra = 1
    fields = ['note', 'author', 'created_at']
    readonly_fields = ['author', 'created_at']
    
    def has_change_permission(self, request, obj=None):
        """Enforce append-only: notes cannot be edited."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Enforce append-only: notes cannot be deleted."""
        return False


@admin.register(PrayerRequest)
class PrayerRequestAdmin(admin.ModelAdmin):
    """
    Phase 13: Comprehensive prayer request admin with privacy controls.
    
    Security:
    - Details excluded from list view for privacy
    - Branch filtering
    - Privacy level indicators
    - Readonly audit fields
    
    Features:
    - Privacy-level color coding
    - Status indicators
    - Comprehensive filtering
    """
    list_display = [
        'get_requester',
        'get_branch',
        'category',
        'privacy_display',
        'status_display',
        'assigned_to',
        'created_at',
    ]
    list_filter = [
        'privacy_level',
        'status',
        'branch',
        'category',
        ('assigned_to', admin.RelatedOnlyFieldListFilter),
        ('answered_at', admin.EmptyFieldListFilter),
        'is_private',  # Legacy field
    ]
    search_fields = [
        'member__first_name',
        'member__last_name',
        'submitted_by_name',
        'details',
    ]
    readonly_fields = [
        'id',
        'created_by',
        'created_at',
        'updated_at',
        'answered_at',
        'is_private',  # Legacy, auto-synced
    ]
    fieldsets = (
        ('Request Information', {
            'fields': (
                'id',
                'branch',
                'member',
                'submitted_by_name',
                'created_by',
            )
        }),
        ('Prayer Details', {
            'fields': (
                'category',
                'details',
            )
        }),
        ('Privacy & Status', {
            'fields': (
                'privacy_level',
                'is_private',  # Show legacy field
                'status',
                'assigned_to',
            )
        }),
        ('Outcome', {
            'fields': (
                'answered_at',
                'closure_reason',
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )
    inlines = [PrayerNoteInline]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def get_requester(self, obj):
        """Display requester with privacy protection."""
        if obj.member:
            return format_html(
                '<span style="font-weight: bold;">{}</span>',
                obj.member.full_name
            )
        elif obj.submitted_by_name:
            return format_html(
                '<span style="font-style: italic;">{} (Anonymous)</span>',
                obj.submitted_by_name
            )
        return format_html('<span style="color: gray;">Anonymous</span>')
    get_requester.short_description = 'Requester'
    
    def get_branch(self, obj):
        """Display branch name."""
        return obj.branch.name if obj.branch else '-'
    get_branch.short_description = 'Branch'
    get_branch.admin_order_field = 'branch__name'
    
    def privacy_display(self, obj):
        """Color-coded privacy level display."""
        colors = {
            'PRIVATE': 'red',
            'PASTORAL': 'orange',
            'FELLOWSHIP': 'blue',
            'PUBLIC': 'green',
        }
        color = colors.get(obj.privacy_level, 'black')
        icons = {
            'PRIVATE': '🔒',
            'PASTORAL': '🛡️',
            'FELLOWSHIP': '👥',
            'PUBLIC': '🌍',
        }
        icon = icons.get(obj.privacy_level, '❓')
        return format_html(
            '{} <span style="color: {}; font-weight: bold;">{}</span>',
            icon,
            color,
            obj.get_privacy_level_display()
        )
    privacy_display.short_description = 'Privacy'
    privacy_display.admin_order_field = 'privacy_level'
    
    def status_display(self, obj):
        """Status with visual indicator."""
        icons = {
            'NEW': '🆕',
            'ASSIGNED': '👤',
            'IN_PROGRESS': '⚙️',
            'FOLLOW_UP': '📅',
            'ANSWERED': '✅',
            'CLOSED': '🔒',
            'CANCELLED': '❌',
        }
        icon = icons.get(obj.status, '❓')
        return format_html(
            '{} {}',
            icon,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'
    
    def save_model(self, request, obj, form, change):
        """Auto-set created_by for staff-entered requests."""
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """
        Phase 13: Branch-scoped admin access.
        Super admins see all, others see only their branch.
        """
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'branch') and request.user.branch:
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(PrayerNote)
class PrayerNoteAdmin(admin.ModelAdmin):
    """
    Phase 13: Prayer notes admin (append-only).
    
    Security:
    - Cannot edit or delete once created
    - Branch-scoped access
    - Author auto-set
    """
    list_display = ['prayer_request', 'author', 'note_preview', 'created_at']
    list_filter = [
        'prayer_request__branch',
        ('author', admin.RelatedOnlyFieldListFilter),
        'created_at',
    ]
    search_fields = ['prayer_request__member__first_name', 'prayer_request__member__last_name', 'note']
    readonly_fields = ['prayer_request', 'author', 'note', 'created_at']
    fields = ['prayer_request', 'author', 'note', 'created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def note_preview(self, obj):
        """Short preview of note content."""
        return obj.note[:100] + '...' if len(obj.note) > 100 else obj.note
    note_preview.short_description = 'Note'
    
    def has_add_permission(self, request):
        """Notes should be added through request admin inline."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Enforce append-only: cannot edit."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Enforce append-only: cannot delete."""
        return False
    
    def get_queryset(self, request):
        """Branch-scoped access."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'branch') and request.user.branch:
            return qs.filter(prayer_request__branch=request.user.branch)
        return qs.none()
