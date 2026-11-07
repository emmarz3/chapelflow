from django.contrib import admin
from django.utils.html import format_html

from .models import PastoralCase, PastoralNote


class PastoralNoteInline(admin.TabularInline):
    """
    Phase 13: Inline pastoral notes with append-only enforcement.
    
    Security:
    - Read-only after creation (append-only)
    - Author auto-set, cannot be changed
    """
    model = PastoralNote
    extra = 1
    fields = ['note', 'author', 'created_at']
    readonly_fields = ['author', 'created_at']
    
    def has_change_permission(self, request, obj=None):
        """Enforce append-only: notes cannot be edited."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Enforce append-only: notes cannot be deleted."""
        return False


@admin.register(PastoralCase)
class PastoralCaseAdmin(admin.ModelAdmin):
    """
    Phase 13: Comprehensive pastoral case admin with security and usability.
    
    Security:
    - Sensitive fields (summary, notes) excluded from list view
    - Branch filtering to prevent cross-branch access
    - Readonly audit fields
    - No deletion to preserve audit trail
    
    Features:
    - Priority-based color coding
    - Status indicators
    - Comprehensive filtering
    - Search by member name
    """
    list_display = [
        'get_member_name',
        'get_branch',
        'category',
        'priority_display',
        'status_display',
        'assigned_to',
        'next_follow_up_date',
        'created_at',
    ]
    list_filter = [
        'priority',
        'status',
        'branch',
        'category',
        ('assigned_to', admin.RelatedOnlyFieldListFilter),
        ('next_follow_up_date', admin.EmptyFieldListFilter),
        ('escalated_at', admin.EmptyFieldListFilter),
        ('closed_at', admin.EmptyFieldListFilter),
    ]
    search_fields = [
        'member__first_name',
        'member__last_name',
        'category',
        'summary',
    ]
    readonly_fields = [
        'id',
        'created_by',
        'created_at',
        'updated_by',
        'updated_at',
        'escalated_by',
        'escalated_at',
        'closed_at',
    ]
    fieldsets = (
        ('Case Information', {
            'fields': (
                'id',
                'branch',
                'member',
                'category',
                'summary',
            )
        }),
        ('Priority & Status', {
            'fields': (
                'priority',
                'status',
                'assigned_to',
                'next_follow_up_date',
            )
        }),
        ('Escalation', {
            'fields': (
                'escalated_at',
                'escalated_by',
                'escalation_reason',
            ),
            'classes': ('collapse',),
        }),
        ('Closure', {
            'fields': (
                'closed_at',
                'closure_reason',
            ),
            'classes': ('collapse',),
        }),
        ('Audit Trail', {
            'fields': (
                'created_by',
                'created_at',
                'updated_by',
                'updated_at',
            ),
            'classes': ('collapse',),
        }),
    )
    inlines = [PastoralNoteInline]
    date_hierarchy = 'created_at'
    ordering = ['-priority', '-created_at']
    
    def get_member_name(self, obj):
        """Display member name with privacy indicator."""
        if obj.member:
            return format_html(
                '<span style="font-weight: bold;">{}</span>',
                obj.member.full_name
            )
        return '-'
    get_member_name.short_description = 'Member'
    get_member_name.admin_order_field = 'member__last_name'
    
    def get_branch(self, obj):
        """Display branch name."""
        return obj.branch.name if obj.branch else '-'
    get_branch.short_description = 'Branch'
    get_branch.admin_order_field = 'branch__name'
    
    def priority_display(self, obj):
        """Color-coded priority display."""
        colors = {
            'URGENT': 'red',
            'HIGH': 'orange',
            'MEDIUM': 'blue',
            'LOW': 'gray',
        }
        color = colors.get(obj.priority, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_display.short_description = 'Priority'
    priority_display.admin_order_field = 'priority'
    
    def status_display(self, obj):
        """Status with visual indicator."""
        icons = {
            'OPEN': '🔵',
            'ASSIGNED': '👤',
            'IN_PROGRESS': '⚙️',
            'FOLLOW_UP': '📅',
            'ESCALATED': '⚠️',
            'RESOLVED': '✅',
            'CLOSED': '🔒',
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
        """Auto-set created_by and updated_by."""
        if not change:  # New object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion to preserve audit trail."""
        return False
    
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


@admin.register(PastoralNote)
class PastoralNoteAdmin(admin.ModelAdmin):
    """
    Phase 13: Pastoral notes admin (append-only).
    
    Security:
    - Cannot edit or delete once created
    - Branch-scoped access
    - Author auto-set
    """
    list_display = ['case', 'author', 'note_preview', 'created_at']
    list_filter = [
        'case__branch',
        ('author', admin.RelatedOnlyFieldListFilter),
        'created_at',
    ]
    search_fields = ['case__member__first_name', 'case__member__last_name', 'note']
    readonly_fields = ['case', 'author', 'note', 'created_at']
    fields = ['case', 'author', 'note', 'created_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def note_preview(self, obj):
        """Short preview of note content."""
        return obj.note[:100] + '...' if len(obj.note) > 100 else obj.note
    note_preview.short_description = 'Note'
    
    def has_add_permission(self, request):
        """Notes should be added through case admin inline."""
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
            return qs.filter(case__branch=request.user.branch)
        return qs.none()
