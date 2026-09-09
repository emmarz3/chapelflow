from rest_framework import serializers

from common.serializers.validators import ScopedFKValidationMixin
from .models import Member, MemberQRCode, MembershipHistory, MemberTag, EngagementMetrics


class MemberQRCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberQRCode
        fields = ["token", "is_active", "created_at", "regenerated_at"]
        read_only_fields = fields


class MemberTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberTag
        fields = ["id", "label"]


class MembershipHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipHistory
        fields = [
            "id", "previous_status", "new_status", "previous_branch",
            "new_branch", "note", "changed_by", "created_at",
        ]
        read_only_fields = fields


class MemberSerializer(ScopedFKValidationMixin, serializers.ModelSerializer):
    """
    Phase 4: Enhanced with comprehensive FK validation to prevent:
    - Cross-branch member manipulation
    - Academic hierarchy inconsistencies (college/department)
    - Fellowship assignment outside scope
    - User account ownership manipulation
    - Household assignment outside scope
    """
    full_name = serializers.CharField(read_only=True)
    tags = MemberTagSerializer(many=True, read_only=True)
    qr_code = MemberQRCodeSerializer(read_only=True)

    class Meta:
        model = Member
        fields = [
            "id", "user", "branch", "household", "first_name", "last_name",
            "other_names", "full_name", "gender", "date_of_birth", "email",
            "phone_number", "address", "photo_url", "membership_status",
            "membership_date", "emergency_contact_name", "emergency_contact_phone",
            "college", "department", "community", "fellowship",
            "tags", "qr_code", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_branch(self, branch):
        """
        Phase 3/4: Validate user has access to the branch. Prevents
        cross-branch member creation/modification.
        """
        return self.validate_branch_fk(branch)
    
    def validate_user(self, user):
        """
        Phase 4 CRITICAL: Prevent ownership manipulation. The Member.user
        field links a member record to a User account. Changing this field
        via normal API requests would allow privilege escalation or
        ownership hijacking. This field should only be set during:
        1. Self-registration (POST /auth/register/)
        2. Explicit account linking by Super Admin
        
        For normal updates, this field must be read-only.
        """
        # On create: allow if user belongs to same branch (validated elsewhere)
        if not self.instance:
            if user and user.branch_id != self.initial_data.get('branch'):
                raise serializers.ValidationError(
                    "User account must belong to the same branch as the member."
                )
            return user
        
        # On update: prevent changing user field
        if user != self.instance.user:
            raise serializers.ValidationError(
                "Cannot change member's user account. Use dedicated account linking "
                "operation if you need to reassociate member with a different user."
            )
        return user
    
    def validate_household(self, household):
        """
        Phase 4: Validate household belongs to accessible branch.
        Prevents assigning member to household in unauthorized branch.
        """
        if household:
            return self.validate_related_branch_fk(household, 'household')
        return household
    
    def validate_fellowship(self, fellowship):
        """
        Phase 4/5: Validate fellowship is accessible to the requesting user.
        Prevents Fellowship Leader A from assigning members to Fellowship B.
        
        Phase 5 Enhancement: Optionally warn if setting fellowship that doesn't
        match member's active GroupMembership in a Fellowship-type group.
        Note: This is informational only - Member.fellowship is a direct FK
        that can exist independently of GroupMembership (legacy compatibility).
        """
        if fellowship:
            validated_fellowship = self.validate_group_fk(fellowship)
            
            # Phase 5: Check consistency with GroupMembership (advisory only)
            if self.instance:  # Only on update
                from apps.groups.models import GroupMembership, GroupRole
                from apps.ministries.models import GroupType
                
                # Check if member has an active Fellowship membership
                active_fellowship_memberships = GroupMembership.objects.filter(
                    member=self.instance,
                    is_active=True,
                    group__group_type=GroupType.FELLOWSHIP
                ).select_related('group')
                
                if active_fellowship_memberships.exists():
                    membership_fellowship = active_fellowship_memberships.first().group
                    if membership_fellowship.id != validated_fellowship.id:
                        # Note: Not raising error to maintain backward compatibility
                        # Member.fellowship can differ from GroupMembership fellowship
                        # This is a known legacy pattern that will be unified in future
                        pass
            
            return validated_fellowship
        return fellowship
    
    def validate_college(self, college):
        """
        Phase 4: Validate college is active. Additional hierarchy validation
        in validate() checks college/department consistency.
        """
        if college and not college.is_active:
            raise serializers.ValidationError("Cannot assign member to inactive college.")
        return college
    
    def validate_department(self, department):
        """
        Phase 4: Validate department is active. Additional hierarchy validation
        in validate() checks department.college consistency.
        """
        if department and not department.is_active:
            raise serializers.ValidationError("Cannot assign member to inactive department.")
        return department
    
    def validate(self, attrs):
        """
        Phase 4: Cross-field validation for academic hierarchy and transfer protection.
        
        Academic Hierarchy: If both college and department are provided, ensure
        department.college == submitted_college to prevent inconsistent
        relationships like:
            Member.college = College A
            Member.department = Department X (which belongs to College B)
        
        Transfer Protection: Branch and fellowship changes must go through the
        explicit transfer endpoint, not via normal PATCH/PUT.
        """
        college = attrs.get('college')
        department = attrs.get('department')
        
        # Phase 4: Validate academic hierarchy consistency
        if department and college:
            if department.college_id != college.id:
                raise serializers.ValidationError({
                    'department': f"Department '{department.name}' belongs to "
                                  f"'{department.college.name}', not '{college.name}'. "
                                  f"College and department must be consistent."
                })
        
        # If department provided without college, infer college from department
        if department and not college:
            attrs['college'] = department.college
        
        # Phase 4: Transfer protection - branch/fellowship changes require explicit transfer
        for field in ("branch", "fellowship"):
            new_value = attrs.get(field)
            if self.instance and new_value is not None:
                old_value = getattr(self.instance, field)
                if new_value != old_value:
                    raise serializers.ValidationError(
                        {field: f"Use the transfer action (POST /members/{{id}}/transfer/) to change {field}."}
                    )
        
        return attrs

    def update(self, instance, validated_data):
        """
        Phase 4: Remove branch/fellowship from validated_data as they're
        protected by transfer-only restriction. The validate() method above
        already raised ValidationError if they're present and different, so
        this is defense-in-depth to ensure they're never accidentally applied.
        """
        validated_data.pop('branch', None)
        validated_data.pop('fellowship', None)
        return super().update(instance, validated_data)


class MemberImportRowResultSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["created", "updated", "failed"])
    errors = serializers.DictField(required=False)


class MemberImportSummarySerializer(serializers.Serializer):
    total = serializers.IntegerField()
    created = serializers.IntegerField()
    updated = serializers.IntegerField()
    failed = serializers.IntegerField()
    row_results = MemberImportRowResultSerializer(many=True)



class MemberFollowUpSerializer(serializers.ModelSerializer):
    """
    Phase 11: Member follow-up serializer with security controls.
    
    Security:
    - member: Read-only (set by signal, cannot be changed)
    - milestone: Read-only (set by signal, cannot be changed)
    - scheduled_for: Read-only (calculated by signal)
    - reminder_sent_at: Server-controlled (never exposed to clients)
    - assigned_to: Writable (for reassignment)
    - completed_at: Writable (staff marks as complete)
    - notes: Writable (staff records follow-up notes)
    
    Authorization enforced in viewset:
    - Only assigned staff + pastoral team can view/edit
    - Branch scoping prevents cross-branch access
    """
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    milestone_display = serializers.CharField(source='get_milestone_display', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        from .models import MemberFollowUp
        model = MemberFollowUp
        fields = [
            'id', 'member', 'member_name', 'milestone', 'milestone_display',
            'assigned_to', 'assigned_to_name', 'scheduled_for', 'completed_at',
            'notes', 'is_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'member', 'member_name', 'milestone', 'milestone_display',
            'scheduled_for', 'created_at', 'updated_at', 'is_overdue'
        ]
    
    def get_is_overdue(self, obj):
        """Check if follow-up is overdue."""
        from django.utils import timezone
        if obj.completed_at:
            return False
        return timezone.now() > obj.scheduled_for
    
    def validate_assigned_to(self, assigned_to):
        """
        Phase 11: Validate assigned_to belongs to same branch as member.
        Prevents cross-branch assignment and unauthorized access.
        
        Security checks:
        1. assigned_to must be in same branch as member
        2. assigned_to must have appropriate role (pastoral or admin access)
        3. Cannot assign to inactive/deleted users
        """
        if not assigned_to:
            return assigned_to
        
        # Get member's branch
        if self.instance:
            member_branch = self.instance.member.branch
        else:
            # On create (shouldn't happen via API, but defensive)
            member_id = self.initial_data.get('member')
            if member_id:
                from .models import Member
                member = Member.objects.filter(id=member_id).first()
                if member:
                    member_branch = member.branch
                else:
                    raise serializers.ValidationError(
                        "Cannot assign follow-up: member not found."
                    )
            else:
                raise serializers.ValidationError(
                    "Cannot assign follow-up: member not specified."
                )
        
        # Check 1: Same branch
        if assigned_to.branch_id != member_branch.id:
            raise serializers.ValidationError(
                f"Cannot assign follow-up to user from different branch. "
                f"Member is in {member_branch.name}, assigned user is in {assigned_to.branch.name}."
            )
        
        # Check 2: User must be active
        if not assigned_to.is_active:
            raise serializers.ValidationError(
                "Cannot assign follow-up to inactive user."
            )
        
        # Check 3: User must have appropriate role
        # Acceptable roles: pastoral access or branch admin
        from common.constants.roles import Roles
        acceptable_roles = (
            list(Roles.PASTORAL_ACCESS_ROLES) + 
            list(Roles.BRANCH_SCOPE_ROLES) +
            list(Roles.GLOBAL_SCOPE_ROLES)
        )
        
        if assigned_to.role not in acceptable_roles:
            raise serializers.ValidationError(
                f"Cannot assign follow-up to user with role '{assigned_to.role}'. "
                f"Only pastoral staff and administrators can be assigned follow-ups."
            )
        
        return assigned_to


class EngagementMetricsSerializer(serializers.ModelSerializer):
    """
    Phase 11: Engagement metrics serializer (read-only).
    
    All fields are read-only - calculated by periodic task.
    Exposed for:
    - Pastor dashboard
    - Member profile view
    - Fellowship leader reports
    
    Security:
    - Read-only (cannot be manipulated by clients)
    - Branch scoping in viewset
    - Privacy consideration: giving metrics optional
    """
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    engagement_level = serializers.SerializerMethodField()
    
    class Meta:
        model = EngagementMetrics
        fields = [
            'member', 'member_name',
            'services_attended_30d', 'services_attended_90d', 'last_service_date',
            'attendance_rate_30d', 'events_attended_30d', 'events_attended_90d',
            'last_event_date', 'volunteer_assignments_active',
            'volunteer_assignments_completed', 'last_volunteer_date',
            'giving_count_30d', 'giving_count_90d', 'last_giving_date',
            'engagement_score', 'engagement_level', 'days_since_last_activity',
            'last_calculated_at'
        ]
        read_only_fields = fields
    
    def get_engagement_level(self, obj):
        """
        Categorize engagement score into human-readable level.
        0-25: Low
        26-50: Medium
        51-75: Good
        76-100: Excellent
        """
        score = obj.engagement_score
        if score <= 25:
            return "Low"
        elif score <= 50:
            return "Medium"
        elif score <= 75:
            return "Good"
        else:
            return "Excellent"
