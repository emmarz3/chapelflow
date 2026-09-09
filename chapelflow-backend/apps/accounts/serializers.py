from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from common.constants.roles import Roles
from .models import InstitutionalAccountControl, Permission, RolePermission, User


class UserPublicSerializer(serializers.ModelSerializer):
    effective_permissions = serializers.SerializerMethodField()

    def get_effective_permissions(self, user):
        """Return the server-evaluated grants used by the web client manifest."""
        if user.get_role_code() == Roles.SUPER_ADMIN:
            return ["*"]
        grants = RolePermission.objects.filter(legacy_role_code=user.get_role_code())
        if user.role_obj_id:
            dynamic = RolePermission.objects.filter(role_obj=user.role_obj)
            if dynamic.exists():
                grants = dynamic
        return list(grants.values_list("permission__code", flat=True).distinct())

    class Meta:
        model = User
        fields = [
            "id", "email", "matric_no", "first_name", "last_name",
            "full_name", "phone_number", "role", "branch", "mfa_enabled",
            "is_active", "password_change_required", "date_joined", "effective_permissions",
        ]
        read_only_fields = fields


class StudentSelfProfileSerializer(serializers.Serializer):
    """The deliberately small set of fields a student may change themselves."""

    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    photo_url = serializers.URLField(required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        user = self.context["request"].user
        if User.objects.exclude(pk=user.pk).filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email address is already in use.")
        return value.lower()


class InstitutionalAccountSerializer(serializers.ModelSerializer):
    """Super-admin-only serializer; intentionally never exposes credentials."""

    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    role = serializers.ChoiceField(choices=[
        ("CHAPLAIN", "Chaplain"), ("STUDENT_CHAPLAIN", "Student Chaplain"),
        ("UNIT_HEAD", "Unit leader"), ("FELLOWSHIP_LEADER", "Fellowship leader"),
        ("ATTENDANCE_USHER", "Attendance usher"),
    ])
    last_login = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "phone_number", "role", "branch",
            "institutional_group", "is_active", "password_change_required", "date_joined",
            "last_login", "last_login_ip", "created_by", "password",
        ]
        read_only_fields = ["id", "date_joined", "last_login", "last_login_ip", "created_by"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": ["An initial password is required."]})
        if self.instance is None and not attrs.get("branch"):
            from apps.organizations.models import Branch
            attrs["branch"] = (
                Branch.objects.filter(name__iexact="Chrisland University Chapel", is_active=True).first()
                or Branch.objects.filter(branch_type="CHAPEL", is_active=True).order_by("name").first()
            )
            if not attrs["branch"]:
                raise serializers.ValidationError({"branch": ["Chrisland University Chapel is not configured yet."]})
        role = attrs.get("role", self.instance.role if self.instance else "")
        group = attrs.get("institutional_group", self.instance.institutional_group if self.instance else None)
        if role == "ATTENDANCE_USHER" and group:
            raise serializers.ValidationError({"institutional_group": ["Usher accounts cannot be assigned to a group."]})
        expected_group_types = {"FELLOWSHIP_LEADER": "FELLOWSHIP", "UNIT_HEAD": "UNIT"}
        if group and role in expected_group_types and group.group_type != expected_group_types[role]:
            raise serializers.ValidationError({"institutional_group": [f"This role must be assigned to a {expected_group_types[role].lower()}."]})
        if group and role not in expected_group_types:
            raise serializers.ValidationError({"institutional_group": ["Only unit and fellowship leaders can be assigned to a chapel group."]})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        password = validated_data.pop("password")
        with transaction.atomic():
            if validated_data.get("role") == "ATTENDANCE_USHER":
                # A migration-created singleton makes the count+create critical section lockable.
                control, _ = InstitutionalAccountControl.objects.get_or_create(singleton=1)
                InstitutionalAccountControl.objects.select_for_update().get(pk=control.pk)
                if User.objects.filter(role="ATTENDANCE_USHER", is_active=True).count() >= 2:
                    raise serializers.ValidationError({"role": ["Only two active Attendance Usher accounts are allowed."]})
            account = User(**validated_data, created_by=request.user)
            account.set_password(password)
            account.save()
        return account

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        # The account-management API never permits role escalation or a super-admin target.
        if "role" in validated_data and instance.role == "SUPER_ADMIN":
            raise serializers.ValidationError({"role": ["The Super Admin role cannot be changed here."]})
        target_role = validated_data.get("role", instance.role)
        target_active = validated_data.get("is_active", instance.is_active)
        with transaction.atomic():
            if target_role == "ATTENDANCE_USHER" and target_active:
                control, _ = InstitutionalAccountControl.objects.get_or_create(singleton=1)
                InstitutionalAccountControl.objects.select_for_update().get(pk=control.pk)
                if User.objects.filter(role="ATTENDANCE_USHER", is_active=True).exclude(pk=instance.pk).count() >= 2:
                    raise serializers.ValidationError({"role": ["Only two active Attendance Usher accounts are allowed."]})
            for field, value in validated_data.items():
                setattr(instance, field, value)
            if password:
                instance.set_password(password)
                instance.password_change_required = True
            instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    """
    Accepts either `matric_no` or `email` as the identifier, matching the
    two supported login flows (student/member vs staff/admin).
    """
    matric_no = serializers.CharField(required=False, allow_blank=False)
    email = serializers.EmailField(required=False, allow_blank=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    otp = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        matric_no = attrs.get("matric_no")
        email = attrs.get("email")
        password = attrs.get("password")

        if not matric_no and not email:
            raise serializers.ValidationError({"matric_no": ["Provide a matriculation number or an email."]})

        identifier = matric_no or email
        user = authenticate(request=self.context.get("request"), username=identifier, password=password)

        if user is None:
            raise serializers.ValidationError({"non_field_errors": ["Invalid credentials."]})
        if not user.is_active:
            raise serializers.ValidationError({"non_field_errors": ["This account has been deactivated."]})

        attrs["user"] = user
        return attrs

    def create_tokens(self, user):
        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        refresh["branch_id"] = str(user.branch_id) if user.branch_id else None
        return {"access": str(refresh.access_token), "refresh": str(refresh)}


class RegisterSerializer(serializers.Serializer):
    """
    Public self-registration (spec section 3, mandatory pipeline):
    User account created -> Member record automatically created ->
    Member becomes available to Chapel. This is the ONLY normal path a
    Member is created through; see apps.members.views.MemberViewSet.create
    for why manual admin creation is blocked.
    """
    email = serializers.EmailField(required=False, allow_blank=False)
    matric_no = serializers.CharField(required=False, allow_blank=False)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    branch = serializers.UUIDField(required=False)
    gender = serializers.ChoiceField(choices=[("MALE", "Male"), ("FEMALE", "Female")], required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    college = serializers.UUIDField(required=False, allow_null=True)
    department = serializers.UUIDField(required=False, allow_null=True)
    community = serializers.ChoiceField(choices=[("STUDENT", "Student"), ("STAFF", "Staff Community")], required=False, allow_blank=True)

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_college(self, value):
        if value is None:
            return None
        from apps.university.models import College
        try:
            return College.objects.get(pk=value)
        except College.DoesNotExist:
            raise serializers.ValidationError("College not found.")

    def validate_branch(self, value):
        from apps.organizations.models import Branch
        try:
            return Branch.objects.get(pk=value)
        except Branch.DoesNotExist:
            raise serializers.ValidationError("Branch not found.")

    def validate_department(self, value):
        if value is None:
            return None
        from apps.university.models import Department
        try:
            return Department.objects.get(pk=value)
        except Department.DoesNotExist:
            raise serializers.ValidationError("Department not found.")

    def validate_email(self, value):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_matric_no(self, value):
        if not value:
            return value
        from .validators import normalize_matric_no
        normalized = normalize_matric_no(value)
        if User.objects.filter(matric_no=normalized).exists():
            raise serializers.ValidationError("An account with this matriculation number already exists.")
        return value

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("matric_no"):
            raise serializers.ValidationError({"email": ["Provide an email or a matriculation number."]})
        if not attrs.get("branch"):
            from apps.organizations.models import Branch
            attrs["branch"] = (
                Branch.objects.filter(name__iexact="Chrisland University Chapel", is_active=True).first()
                or Branch.objects.filter(branch_type="CHAPEL", is_active=True).order_by("name").first()
            )
            if not attrs["branch"]:
                raise serializers.ValidationError({"branch": ["Chrisland University Chapel is not configured yet."]})
        return attrs

    def create(self, validated_data):
        from django.db import IntegrityError

        from apps.members.services import self_register_member

        try:
            return self_register_member(validated_data)
        except IntegrityError:
            # Belt-and-braces for the race between validate_email/
            # validate_matric_no's existence check and this create() --
            # two concurrent registrations for the same identifier can
            # both pass validation before either commits. Surface it as
            # a normal validation error rather than a 500.
            raise serializers.ValidationError(
                {"non_field_errors": ["An account with these details already exists."]}
            )


class MFAConfirmSerializer(serializers.Serializer):
    """POST /api/v1/auth/mfa/confirm/ body — a bare 6-digit TOTP code."""
    otp = serializers.RegexField(regex=r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code from your authenticator app."})


class MFAResetSerializer(serializers.Serializer):
    """
    POST /api/v1/auth/mfa/reset/ body — administrative reset for a user
    who lost their authenticator device. `user_id` identifies the target;
    permission (Chapel Admin / Super Admin) is enforced by the view, not
    here — this serializer only validates input shape.
    """
    user_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "description"]


class PermissionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["code", "description"]

    def validate_code(self, value):
        if Permission.objects.filter(code=value).exists():
            raise serializers.ValidationError("A permission with this code already exists.")
        return value


class RolePermissionSummarySerializer(serializers.Serializer):
    """One row per known role (Roles.CURRENT_CHOICES only -- legacy roles
    are not exposed for new assignment here, matching RegisterSerializer
    and every other new-role-facing surface in this codebase), with the
    permission codes currently granted to it."""
    role = serializers.CharField()
    label = serializers.CharField()
    permission_codes = serializers.ListField(child=serializers.CharField())


class RolePermissionAssignSerializer(serializers.Serializer):
    permission_code = serializers.CharField()

    def validate_permission_code(self, value):
        if not Permission.objects.filter(code=value).exists():
            raise serializers.ValidationError("Unknown permission code.")
        return value
