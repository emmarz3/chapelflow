import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from common.constants.roles import Roles
from .validators import normalize_matric_no, validate_matric_no


class ScopeType(models.TextChoices):
    """
    Organizational scope of a role (Phase 3). Determines what data
    a user with this role can access.
    """
    GLOBAL = "GLOBAL", "Global (all organizations)"
    ORG_WIDE = "ORG_WIDE", "Organization-wide"
    BRANCH = "BRANCH", "Branch-only"
    ASSIGNMENT = "ASSIGNMENT", "Assignment-based (Fellowship/Unit/Group)"
    SELF = "SELF", "Self-only"


class Role(models.Model):
    """
    Phase 3: Database-backed role definition for dynamic RBAC.
    
    System roles (is_system=True) are seeded from constants and cannot be
    deleted, only deactivated. Custom roles (is_system=False) can be freely
    created/deleted by administrators with appropriate permissions.
    
    This coexists with the legacy User.role CharField during migration - see
    User.get_role_code() and User.get_role_obj() for backward compatibility.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Identity
    code = models.CharField(
        max_length=32, unique=True, db_index=True,
        help_text="Unique role code, e.g. 'SUPER_ADMIN', 'FELLOWSHIP_LEADER'"
    )
    name = models.CharField(max_length=100, help_text="Display name for UI")
    description = models.TextField(blank=True)
    
    # Scope configuration
    scope_type = models.CharField(
        max_length=20, choices=ScopeType.choices,
        help_text="Determines what organizational scope this role can access"
    )
    
    # For ASSIGNMENT scope type: which group types can be led
    assignment_group_types = models.JSONField(
        default=list, blank=True,
        help_text="For ASSIGNMENT scope: ['FELLOWSHIP'] | ['UNIT'] | ['MINISTRY']"
    )
    
    # Metadata
    is_system = models.BooleanField(
        default=False,
        help_text="System role (seeded from code), cannot be deleted"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive roles cannot be assigned to new users"
    )
    requires_mfa = models.BooleanField(
        default=False,
        help_text="Users with this role must complete MFA enrollment"
    )
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    
    class Meta:
        db_table = "accounts_role"
        ordering = ["name"]
    
    def __str__(self):
        return self.name
    
    def delete(self, *args, **kwargs):
        """Prevent deletion of system roles."""
        if self.is_system:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Cannot delete system role '{self.code}'.")
        return super().delete(*args, **kwargs)


class InstitutionalAccountControl(models.Model):
    """Singleton row locked while an usher account is provisioned."""

    singleton = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    class Meta:
        db_table = "accounts_institutional_account_control"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email=None, matric_no=None, password=None, **extra_fields):
        if not email and not matric_no:
            raise ValueError("A user must have either an email or a matriculation number.")

        email = self.normalize_email(email) if email else None
        matric_no = normalize_matric_no(matric_no) if matric_no else None

        user = self.model(email=email, matric_no=matric_no, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, matric_no=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", Roles.MEMBER)
        return self._create_user(email, matric_no, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Roles.SUPER_ADMIN)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, None, password, **extra_fields)

    def get_by_natural_key(self, identifier):
        """Allow authenticate() to look users up by email OR matric_no."""
        normalized = normalize_matric_no(identifier)
        return self.get(models.Q(email__iexact=identifier) | models.Q(matric_no=normalized))


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model. Internal identity is a UUID; matric_no and email are
    separate, optional-but-at-least-one-required identifiers.
    Never use matric_no as the primary key.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(unique=True, null=True, blank=True)
    matric_no = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        validators=[validate_matric_no],
        help_text="Institutional identifier, e.g. SWE/2024/005. Not all users have one.",
    )

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)

    # PHASE 3: Dual role system for backward compatibility
    # LEGACY: Keep for backward compatibility during migration
    role = models.CharField(
        max_length=32, null=True, blank=True, db_index=True,
        help_text="LEGACY: Use role_obj for new code. Kept for backward compatibility."
    )
    
    # NEW: Dynamic role FK (Phase 3+)
    role_obj = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.PROTECT,
        related_name="users",
        help_text="Phase 3: Dynamic role assignment"
    )
    
    branch = models.ForeignKey(
        "organizations.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    password_change_required = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_accounts",
    )
    institutional_group = models.ForeignKey(
        "ministries.Group", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="institutional_accounts",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "accounts_user"
        indexes = [
            models.Index(fields=["matric_no"]),
            models.Index(fields=["email"]),
            models.Index(fields=["role"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["role"], condition=models.Q(role=Roles.SUPER_ADMIN),
                name="exactly_one_super_admin",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.matric_no:
            self.matric_no = normalize_matric_no(self.matric_no)
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if not self.email and not self.matric_no:
            from django.core.exceptions import ValidationError
            raise ValidationError("A user requires either an email or a matriculation number.")

    def __str__(self):
        return self.matric_no or self.email or str(self.id)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_role_code(self) -> str:
        """
        Phase 3: Get role code for authorization checks. Tries role_obj first
        (Phase 3+), falls back to legacy role field (Phase 0-2).
        
        This ensures both old code (checking user.role == Roles.SUPER_ADMIN)
        and new code work correctly during the migration period.
        """
        if self.role_obj_id:
            return self.role_obj.code
        return self.role or Roles.MEMBER
    
    def get_role_obj(self):
        """
        Phase 3: Get Role object, works with both legacy and new systems.
        
        If user has role_obj FK set, returns that. Otherwise, during
        migration, looks up or creates a Role object from the legacy
        role code so new code expecting a Role object continues working.
        """
        if self.role_obj:
            return self.role_obj
        # During migration: create/get Role object from legacy code
        if self.role:
            return self._get_legacy_role_as_obj()
        return None
    
    def _get_legacy_role_as_obj(self):
        """
        Phase 3 migration helper: Create a virtual Role object from legacy
        role code. Cached to avoid repeated DB lookups.
        """
        cache_key = f"legacy_role_obj:{self.role}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Look up or create Role object for legacy code
        try:
            role_obj = Role.objects.get(code=self.role)
        except Role.DoesNotExist:
            # Fallback: create from constants (should only happen during migration)
            role_obj = Role.objects.create(
                code=self.role,
                name=dict(Roles.CHOICES).get(self.role, self.role),
                is_system=True,
                is_active=True,
                scope_type=self._infer_scope_type(self.role),
                requires_mfa=self.role in Roles.PRIVILEGED_ROLES,
            )
        
        cache.set(cache_key, role_obj, 3600)  # Cache 1 hour
        return role_obj
    
    def _infer_scope_type(self, role_code):
        """Map legacy role codes to scope types."""
        if role_code in Roles.GLOBAL_SCOPE_ROLES:
            return ScopeType.GLOBAL
        if role_code in Roles.ORG_WIDE_SCOPE_ROLES:
            return ScopeType.ORG_WIDE
        if role_code in Roles.ASSIGNMENT_SCOPED_ROLES:
            return ScopeType.ASSIGNMENT
        if role_code == Roles.MEMBER:
            return ScopeType.SELF
        return ScopeType.BRANCH
    
    def has_scope(self, scope_type: str) -> bool:
        """Phase 3: Check if user's role has given scope type."""
        role_obj = self.get_role_obj()
        if not role_obj:
            return False
        return role_obj.scope_type == scope_type
    
    def user_requires_mfa(self) -> bool:
        """Phase 3: Check if user's role requires MFA."""
        role_obj = self.get_role_obj()
        if not role_obj:
            return False
        return role_obj.requires_mfa

    def has_perm_code(self, code: str) -> bool:
        """
        Phase 3: Check permission (works with both legacy and new system).
        
        Super Admin always bypasses. For others, checks RolePermission
        via either the new role_obj FK or the legacy role code.
        """
        role_code = self.get_role_code()
        if role_code == Roles.SUPER_ADMIN:
            return True
        
        # Try new system first (role_obj)
        if self.role_obj_id:
            dynamic_permissions = RolePermission.objects.filter(role_obj=self.role_obj)
            if dynamic_permissions.exists():
                return dynamic_permissions.filter(permission__code=code).exists()
            # During the staged Role migration, old deployments can have a
            # role_obj on users while permissions still live in the legacy
            # role column. Preserve access until those grants are migrated;
            # once a dynamic grant exists, it remains authoritative.
        
        # Fall back to legacy system (role string)
        return RolePermission.objects.filter(
            legacy_role_code=role_code,
            permission__code=code
        ).exists()


class Permission(models.Model):
    """
    Phase 3: Enhanced fine-grained action permissions.
    
    Permissions are stored in the database and can be assigned to roles
    dynamically. Seeded by scripts/seed_roles.py but can be extended
    at runtime by administrators.
    """
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=100, help_text="Human-readable name")
    description = models.TextField(blank=True)
    
    # Phase 3: Categorization
    module = models.CharField(
        max_length=50, db_index=True, blank=True,
        help_text="Module name: members, events, finance, etc."
    )
    
    # Phase 3: Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_permission"
        ordering = ["module", "code"]

    def __str__(self):
        return f"{self.code} - {self.name}" if self.name else self.code


class RolePermission(models.Model):
    """
    Phase 3: Maps roles to permissions. Supports BOTH legacy string roles
    (during migration) and new Role objects (Phase 3+).
    
    Exactly one of role_obj or legacy_role_code must be set, enforced
    by a check constraint.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # NEW: FK to Role model (Phase 3+)
    role_obj = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.CASCADE,
        related_name="permissions",
        help_text="Phase 3: Dynamic role FK"
    )
    
    # LEGACY: String role code for backward compatibility
    legacy_role_code = models.CharField(
        max_length=32, null=True, blank=True, db_index=True,
        help_text="LEGACY: For migration only, use role_obj for new code"
    )
    
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="role_grants")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_role_permission"
        # Ensure at least one role reference exists
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(role_obj__isnull=False, legacy_role_code__isnull=True) |
                    models.Q(role_obj__isnull=True, legacy_role_code__isnull=False)
                ),
                name="role_permission_one_role_type"
            )
        ]
        indexes = [
            models.Index(fields=["role_obj", "permission"]),
            models.Index(fields=["legacy_role_code", "permission"]),
        ]

    def __str__(self):
        role_display = self.role_obj.name if self.role_obj else self.legacy_role_code
        return f"{role_display} -> {self.permission.code}"
    
    def save(self, *args, **kwargs):
        """Validate that exactly one role type is set."""
        if bool(self.role_obj_id) == bool(self.legacy_role_code):
            from django.core.exceptions import ValidationError
            raise ValidationError(
                "Exactly one of role_obj or legacy_role_code must be set."
            )
        super().save(*args, **kwargs)


class LoginHistory(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name="login_history")
    identifier_attempted = models.CharField(max_length=150, blank=True, help_text="Raw matric_no/email submitted, for failed-login forensics.")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    successful = models.BooleanField(default=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_login_history"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]


class MFADevice(models.Model):
    """
    TOTP-based MFA device (compatible with django-otp's TOTPDevice shape,
    kept local here to avoid a hard dependency). Enforced for roles listed
    in settings.MFA_ENFORCED_ROLES.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="mfa_device")
    secret = models.CharField(max_length=64)
    confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_mfa_device"


class RoleAssignmentHistory(models.Model):
    """
    Phase 3: Audit trail for role changes. Critical for security review
    and compliance - must know who gave what role to whom and when.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_history")
    
    # Previous role (nullable for first assignment)
    previous_role = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", help_text="Previous role object"
    )
    previous_role_code = models.CharField(
        max_length=32, blank=True,
        help_text="Previous role code (legacy or role_obj.code)"
    )
    
    # New role (nullable for role removal)
    new_role = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", help_text="New role object"
    )
    new_role_code = models.CharField(
        max_length=32, blank=True,
        help_text="New role code (legacy or role_obj.code)"
    )
    
    reason = models.TextField(blank=True, help_text="Reason for role change")
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="role_changes_made"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "accounts_role_assignment_history"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
    
    def __str__(self):
        return f"{self.user} role change: {self.previous_role_code} → {self.new_role_code}"
