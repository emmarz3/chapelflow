from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
import secrets
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from common.constants.roles import Roles
from common.permissions.rbac import IsChapelAdminOrSuperAdmin, IsSuperAdmin
from common.utils.responses import error_response, success_response
from .models import RolePermission
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    MFAConfirmSerializer,
    MFAResetSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PermissionCreateSerializer,
    PermissionSerializer,
    RegisterSerializer,
    RolePermissionAssignSerializer,
    InstitutionalAccountSerializer,
    StudentSelfProfileSerializer,
    UserPublicSerializer,
)
from .services import (
    generate_password_reset_token,
    list_active_sessions,
    record_login,
    revoke_all_sessions,
    revoke_session,
    user_requires_mfa,
)
from .tasks import send_password_reset_email

User = get_user_model()


ACCESS_COOKIE = "chapelflow_access"
REFRESH_COOKIE = "chapelflow_refresh"
CSRF_COOKIE = "chapelflow_csrf"


def _set_auth_cookies(response, access, refresh):
    """Keep browser credentials HttpOnly while preserving bearer-token API use."""
    secure = not settings.DEBUG
    common = {"httponly": True, "secure": secure, "samesite": "Lax"}
    response.set_cookie(ACCESS_COOKIE, access, max_age=15 * 60, **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=7 * 24 * 60 * 60, **common)
    response.set_cookie(
        CSRF_COOKIE, secrets.token_urlsafe(32), max_age=7 * 24 * 60 * 60,
        httponly=False, secure=secure, samesite="Lax",
    )
    return response


def _clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, samesite="Lax")
    response.delete_cookie(REFRESH_COOKIE, samesite="Lax")
    response.delete_cookie(CSRF_COOKIE, samesite="Lax")
    return response


class RegisterView(APIView):
    """
    POST /api/v1/auth/register/ — spec section 3's mandatory public
    self-registration pipeline. This is the ONLY normal way a Member is
    created (see apps.members.views.MemberViewSet.create for the block on
    manual admin creation). AllowAny.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)
        user = serializer.save()
        tokens = RefreshToken.for_user(user)
        response = success_response(
            {"access": str(tokens.access_token), "refresh": str(tokens), "user": UserPublicSerializer(user).data},
            message="Registration successful.",
            status=201,
        )
        return _set_auth_cookies(response, str(tokens.access_token), str(tokens))


class LoginView(APIView):
    """
    POST /api/v1/auth/login/
    Accepts {matric_no, password} for students/members OR
    {email, password} for staff/admins. See serializers.LoginSerializer.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            identifier = request.data.get("matric_no") or request.data.get("email") or ""
            record_login(None, request, successful=False, failure_reason="invalid_credentials", identifier_attempted=str(identifier))
            from apps.audit.models import AuditAction
            from apps.audit.services import write_audit_log
            write_audit_log(AuditAction.LOGIN, "accounts.User", metadata={"successful": False})
            return error_response("Validation failed.", serializer.errors, status=400)

        user = serializer.validated_data["user"]

        if user_requires_mfa(user) and user.mfa_enabled:
            otp = serializer.validated_data.get("otp", "")
            if not _verify_otp(user, otp):
                return error_response(
                    "MFA verification required.",
                    {"otp": ["A valid one-time passcode is required for this account."]},
                    status=401,
                )

        record_login(user, request, successful=True)
        tokens = serializer.create_tokens(user)
        response = success_response(
            {"access": tokens["access"], "refresh": tokens["refresh"], "user": UserPublicSerializer(user).data},
            message="Login successful.",
        )
        return _set_auth_cookies(response, tokens["access"], tokens["refresh"])


def _verify_otp(user, otp: str) -> bool:
    if not otp:
        return False
    try:
        import pyotp
        device = getattr(user, "mfa_device", None)
        if not device or not device.confirmed:
            return False
        return pyotp.TOTP(device.secret).verify(otp, valid_window=1)
    except ImportError:
        # pyotp not installed in this environment; fail closed.
        return False


class MFAEnrollView(APIView):
    """
    POST /api/v1/auth/mfa/enroll/ — spec section 18 (enrollment,
    secret provisioning, QR provisioning). IsAuthenticated: any logged-in
    user can start enrollment, not just roles in MFA_ENFORCED_ROLES —
    someone not yet required to use MFA is still allowed to opt in early.

    Re-enrolling (calling this again) issues a brand new secret and resets
    `confirmed` to False — the old secret stops working immediately, so a
    lost/compromised authenticator app can always be replaced by starting
    over, rather than needing a separate "reset MFA" endpoint.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import pyotp

        from .models import MFADevice

        secret = pyotp.random_base32()
        device, _ = MFADevice.objects.update_or_create(
            user=request.user, defaults={"secret": secret, "confirmed": False},
        )

        issuer = "ChapelFlow CUC"
        account_name = request.user.email or request.user.matric_no or str(request.user.id)
        provisioning_uri = pyotp.totp.TOTP(device.secret).provisioning_uri(name=account_name, issuer_name=issuer)

        qr_code_base64 = None
        try:
            import base64
            import io

            import qrcode

            img = qrcode.make(provisioning_uri)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")
        except ImportError:
            # qrcode isn't installed in every environment; the
            # provisioning_uri alone is enough for any authenticator app
            # that supports manual/URI entry, so this degrades gracefully
            # rather than failing enrollment outright.
            pass

        return success_response(
            {
                "secret": device.secret,
                "provisioning_uri": provisioning_uri,
                "qr_code_base64": qr_code_base64,
            },
            message="Scan the QR code (or enter the secret manually) in your authenticator app, "
                    "then confirm with a 6-digit code via /api/v1/auth/mfa/confirm/.",
        )


class MFAConfirmView(APIView):
    """
    POST /api/v1/auth/mfa/confirm/ {"otp": "123456"} — spec section 18
    (confirmation, verification). Validates the code against the secret
    generated by MFAEnrollView, then flips both MFADevice.confirmed and
    User.mfa_enabled — the latter is what user_requires_mfa()-gated
    permission checks (common.permissions.rbac) actually key off of.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MFAConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)

        from .models import MFADevice

        device = getattr(request.user, "mfa_device", None)
        if not device:
            return error_response(
                "No MFA enrollment in progress. Call /api/v1/auth/mfa/enroll/ first.", status=400
            )

        import pyotp
        if not pyotp.TOTP(device.secret).verify(serializer.validated_data["otp"], valid_window=1):
            return error_response("Invalid or expired code.", {"otp": ["That code doesn't match."]}, status=400)

        device.confirmed = True
        device.save(update_fields=["confirmed"])
        request.user.mfa_enabled = True
        request.user.save(update_fields=["mfa_enabled"])

        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.MFA_ENABLE, "user", str(request.user.id), user=request.user)

        return success_response({"mfa_enabled": True}, message="MFA enabled.")


class MFAResetView(APIView):
    """
    POST /api/v1/auth/mfa/reset/ {"user_id": "...", "reason": "..."} —
    administrative reset for a user who lost their authenticator device.
    Chapel Admin or Super Admin only. A Chapel Admin may only reset users
    within their own branch (Super Admin has no such restriction, per the
    usual global-scope rule elsewhere in this codebase).

    Resets MFADevice.confirmed to False (does NOT delete the device row —
    the user still re-enrolls via the normal /mfa/enroll/ flow, which
    issues a brand new secret anyway) and flips User.mfa_enabled back to
    False, restoring access if MFA is enforced for their role.
    """
    permission_classes = [IsChapelAdminOrSuperAdmin]

    def post(self, request):
        serializer = MFAResetSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)

        target_id = serializer.validated_data["user_id"]
        target = User.objects.filter(pk=target_id).first()
        if not target:
            return error_response("User not found.", status=404)

        if request.user.role == Roles.CHAPEL_ADMIN and target.branch_id != request.user.branch_id:
            # Fail closed with 404, not 403 — consistent with the rest of
            # this codebase's direct-ID handling (avoid confirming another
            # branch's user even exists).
            return error_response("User not found.", status=404)

        from .models import MFADevice

        device = getattr(target, "mfa_device", None)
        if device:
            device.confirmed = False
            device.save(update_fields=["confirmed"])
        target.mfa_enabled = False
        target.save(update_fields=["mfa_enabled"])

        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(
            AuditAction.MFA_RESET, "user", str(target.id), user=request.user,
            metadata={"reason": serializer.validated_data.get("reason", "")},
        )

        return success_response(
            {"user_id": str(target.id), "mfa_enabled": False},
            message="MFA has been reset for this user. They'll need to re-enroll via /api/v1/auth/mfa/enroll/.",
        )


class RefreshView(APIView):
    """
    POST /api/v1/auth/refresh/ {"refresh": "..."}

    Honors SIMPLE_JWT's ROTATE_REFRESH_TOKENS / BLACKLIST_AFTER_ROTATION:
    presenting a refresh token blacklists it and issues a brand new
    refresh+access pair, so a given refresh token is single-use. This
    also means a stolen-then-reused refresh token fails outright once
    the legitimate client has refreshed, which is the whole point of
    rotation -- the previous implementation minted access tokens off
    the same refresh token indefinitely, silently defeating rotation.

    Also re-stamps role/branch_id claims from the current DB state (not
    from the old token), so a refresh after a role/branch change can't
    carry forward stale authorization claims -- consistent with
    LoginSerializer.create_tokens.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        refresh_token = request.data.get("refresh") or request.COOKIES.get(REFRESH_COOKIE)
        if not refresh_token:
            return error_response("Refresh token is required.", status=400)
        try:
            old_refresh = RefreshToken(refresh_token)
        except TokenError:
            return error_response("Invalid or expired refresh token.", status=401)

        user_id = old_refresh.get("user_id")
        user = User.objects.filter(pk=user_id, is_active=True).first()
        if not user:
            return error_response("Invalid or expired refresh token.", status=401)

        # Rotate: blacklist the presented token, issue a fresh pair.
        try:
            old_refresh.blacklist()
        except AttributeError:
            # token_blacklist app not enabled in this environment -- degrade
            # to non-rotating behavior rather than hard-failing.
            pass
        except TokenError:
            return error_response("Invalid or expired refresh token.", status=401)

        new_refresh = RefreshToken.for_user(user)
        new_refresh["role"] = user.role
        new_refresh["branch_id"] = str(user.branch_id) if user.branch_id else None

        response = success_response(
            {"access": str(new_refresh.access_token), "refresh": str(new_refresh)},
            message="Token refreshed.",
        )
        return _set_auth_cookies(response, str(new_refresh.access_token), str(new_refresh))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh") or request.COOKIES.get(REFRESH_COOKIE)
        if not refresh_token:
            return error_response("Refresh token is required.", status=400)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return error_response("Invalid or already-invalidated token.", status=400)
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.LOGOUT, "accounts.User", request.user.id, user=request.user)
        return _clear_auth_cookies(success_response(message="Logged out successfully."))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(UserPublicSerializer(request.user).data)


class InstitutionalAccountListCreateView(APIView):
    """Super-admin control plane for chapel staff accounts, never public users."""
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        accounts = User.objects.exclude(role=Roles.SUPER_ADMIN).filter(
            role__in=["CHAPLAIN", "STUDENT_CHAPLAIN", "UNIT_HEAD", "FELLOWSHIP_LEADER", "ATTENDANCE_USHER"]
        ).select_related("branch", "institutional_group", "created_by").order_by("last_name", "first_name")
        query = request.query_params.get("search")
        if query:
            from django.db.models import Q
            accounts = accounts.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query))
        for field in ("role", "is_active", "institutional_group"):
            value = request.query_params.get(field)
            if value not in (None, ""):
                accounts = accounts.filter(**{field: value})
        return success_response(InstitutionalAccountSerializer(accounts, many=True).data)

    def post(self, request):
        serializer = InstitutionalAccountSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)
        account = serializer.save()
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.CREATE, "accounts.User", account.id, user=request.user,
                        metadata={"role": account.role, "institutional_account": True})
        return success_response(InstitutionalAccountSerializer(account).data, message="Institutional account created.", status=201)


class InstitutionalAccountDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    def _account(self, pk):
        return User.objects.exclude(role=Roles.SUPER_ADMIN).filter(
            pk=pk, role__in=["CHAPLAIN", "STUDENT_CHAPLAIN", "UNIT_HEAD", "FELLOWSHIP_LEADER", "ATTENDANCE_USHER"],
        ).first()

    def get(self, request, pk):
        account = self._account(pk)
        if not account:
            return error_response("Institutional account not found.", status=404)
        return success_response(InstitutionalAccountSerializer(account).data)

    def patch(self, request, pk):
        account = self._account(pk)
        if not account:
            return error_response("Institutional account not found.", status=404)
        serializer = InstitutionalAccountSerializer(account, data=request.data, partial=True, context={"request": request})
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)
        account = serializer.save()
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.UPDATE, "accounts.User", account.id, user=request.user,
                        metadata={"institutional_account": True})
        return success_response(InstitutionalAccountSerializer(account).data, message="Institutional account updated.")


class InstitutionalAccountPasswordResetView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        account = User.objects.exclude(role=Roles.SUPER_ADMIN).filter(pk=pk).first()
        if not account or not account.email:
            return error_response("An institutional account with an email address is required.", status=404)
        uid, token = generate_password_reset_token(account)
        send_password_reset_email.delay(str(account.id), uid, token)
        account.password_change_required = True
        account.save(update_fields=["password_change_required"])
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.PASSWORD_CHANGE, "accounts.User", account.id, user=request.user,
                        metadata={"initiated_by_admin": True})
        return success_response(message="Password reset initiated.")


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return success_response(message="Password changed successfully.")


class StudentProfileView(APIView):
    """Self-service profile endpoint with academic and role fields excluded."""
    permission_classes = [IsAuthenticated]

    def _member(self, request):
        if request.user.get_role_code() != Roles.MEMBER:
            return None
        from apps.members.models import Member
        return Member.objects.filter(user=request.user).first()

    def get(self, request):
        member = self._member(request)
        if member is None:
            return error_response("This profile is available only to student accounts.", status=403)
        return success_response({
            "email": request.user.email,
            "phone_number": request.user.phone_number,
            "address": member.address,
            "photo_url": member.photo_url,
            "emergency_contact_name": member.emergency_contact_name,
            "emergency_contact_phone": member.emergency_contact_phone,
            "matric_no": request.user.matric_no,
            "department": getattr(member.department, "name", None),
            "role": request.user.get_role_code(),
        })

    def patch(self, request):
        member = self._member(request)
        if member is None:
            return error_response("This profile is available only to student accounts.", status=403)
        serializer = StudentSelfProfileSerializer(data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            user_fields = [field for field in ("email", "phone_number") if field in data]
            for field in user_fields:
                setattr(request.user, field, data[field])
            if user_fields:
                request.user.save(update_fields=user_fields)
            member_fields = [field for field in (
                "address", "photo_url", "emergency_contact_name", "emergency_contact_phone",
            ) if field in data]
            for field in member_fields:
                setattr(member, field, data[field])
            if "email" in data:
                member.email = data["email"]
                member_fields.append("email")
            if "phone_number" in data:
                member.phone_number = data["phone_number"]
                member_fields.append("phone_number")
            if member_fields:
                member.save(update_fields=list(set(member_fields)))
        return self.get(request)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email__iexact=email).first()
        if user:
            uid, token = generate_password_reset_token(user)
            send_password_reset_email.delay(str(user.id), uid, token)

        # Always return 200 regardless of whether the email exists,
        # to avoid leaking which emails are registered.
        return success_response(message="If that email exists, a reset link has been sent.")


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            uid = force_str(urlsafe_base64_decode(data["uid"]))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return error_response("Invalid reset link.", status=400)

        if not default_token_generator.check_token(user, data["token"]):
            return error_response("Invalid or expired reset link.", status=400)

        user.set_password(data["new_password"])
        user.save(update_fields=["password"])

        # A password reset means any credential compromise is over --
        # kill every other logged-in session so a stolen session can't
        # outlive the very reset meant to shut it down.
        revoke_all_sessions(user)

        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.PASSWORD_CHANGE,
                         "user", str(user.id), user=user)

        return success_response(message="Password reset successfully.")


class SessionListView(APIView):
    """
    GET /api/v1/auth/sessions/ -- lists this user's active (unexpired,
    non-blacklisted) refresh tokens as "sessions". Note: only jti,
    issued_at and expires_at are available -- OutstandingToken does not
    capture IP/device, so this cannot yet show "Chrome on Windows, Lagos"
    style device info. Wiring that up would mean capturing IP/user-agent
    at token-issue time (login/refresh) into a side table keyed by jti;
    left as follow-up rather than faked here.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = list_active_sessions(request.user)
        current_jti = getattr(request.auth, "get", lambda *_: None)("jti") if request.auth else None
        data = [
            {
                "jti": token.jti,
                "created_at": token.created_at,
                "expires_at": token.expires_at,
                "is_current": token.jti == current_jti,
            }
            for token in sessions
        ]
        return success_response(data)


class SessionRevokeView(APIView):
    """POST /api/v1/auth/sessions/revoke/ {"jti": "..."} -- revoke one
    of the caller's own sessions. Scoped to request.user in the service
    layer, so a jti belonging to another user's session 404s rather than
    silently succeeding or leaking whether it exists."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        jti = request.data.get("jti")
        if not jti:
            return error_response("jti is required.", status=400)
        if not revoke_session(request.user, jti):
            return error_response("Session not found.", status=404)
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.LOGOUT, "accounts.Session", jti, user=request.user, metadata={"revoked": True})
        return success_response(message="Session revoked.")


class SessionRevokeAllView(APIView):
    """POST /api/v1/auth/sessions/revoke-all/ -- revoke every session for
    the caller. Body {"keep_current": true} keeps the session tied to the
    access token used for this request alive (useful for a "log out all
    other devices" UI action rather than logging yourself out too)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_jti = None
        if request.data.get("keep_current"):
            current_jti = getattr(request.auth, "get", lambda *_: None)("jti") if request.auth else None
        count = revoke_all_sessions(request.user, except_jti=current_jti)
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.LOGOUT, "accounts.Session", user=request.user, metadata={"revoked": count})
        return success_response({"revoked": count}, message="Sessions revoked.")


class PermissionListCreateView(APIView):
    """
    GET /api/v1/auth/permissions/ -- the full permission-code catalog.
    POST /api/v1/auth/permissions/ -- register a new permission code
    (e.g. when a new app/feature needs one). Super Admin only: adding a
    code doesn't grant it to anyone by itself (RolePermission does that),
    but the catalog itself should only grow deliberately.
    """
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        return success_response(PermissionSerializer(Permission.objects.order_by("code"), many=True).data)

    def post(self, request):
        serializer = PermissionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)
        permission = serializer.save()

        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.PERMISSION_CHANGE,
                         "accounts.Permission", str(permission.id), user=request.user,
                         metadata={"action": "permission_created", "code": permission.code})

        return success_response(PermissionSerializer(permission).data, status=201)


class RoleListView(APIView):
    """
    GET /api/v1/auth/roles/ -- every currently-assignable role
    (Roles.CURRENT_CHOICES; legacy roles are deliberately excluded, same
    as everywhere else new-role-facing) with the permission codes
    currently granted to it. This is the read side of role administration
    -- see RolePermissionView for assign/remove.

    NOTE ON SCOPE: roles here are the fixed set in common.constants.roles
    .Roles, not DB rows -- there is no create-a-brand-new-role or
    deactivate-a-role operation, because roles aren't dynamic in this
    codebase yet (User.role is a CharField choices, not an FK to a Role
    table). What IS dynamic, and is what this endpoint manages, is which
    permission codes each fixed role holds. Turning roles fully dynamic
    (per-role active flag, scope type, MFA policy as DB fields) is a
    larger schema change touching every app that reads user.role, and is
    intentionally not done here -- flagged as deferred, not silently
    skipped.
    """
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        from common.constants.roles import Roles

        grants = {}
        for role, permission_code in RolePermission.objects.select_related("permission").values_list(
            "role", "permission__code"
        ):
            grants.setdefault(role, []).append(permission_code)

        data = [
            {"role": role, "label": label, "permission_codes": sorted(grants.get(role, []))}
            for role, label in Roles.CURRENT_CHOICES
        ]
        return success_response(data)


class RolePermissionView(APIView):
    """
    POST /api/v1/auth/roles/{role}/permissions/ {"permission_code": "..."}
        -- grant a permission code to a role.
    DELETE /api/v1/auth/roles/{role}/permissions/ {"permission_code": "..."}
        -- revoke it.

    Super Admin only, per spec ("protect these endpoints aggressively").
    SUPER_ADMIN itself is never a valid target -- it implicitly passes
    every permission check (see HasRolePermission), so granting/revoking
    RolePermission rows for it would be a no-op that could mislead an
    admin into thinking it changes anything.
    """
    permission_classes = [IsSuperAdmin]

    def _validate_role(self, role: str):
        from common.constants.roles import Roles
        if role == Roles.SUPER_ADMIN:
            return error_response("SUPER_ADMIN implicitly has every permission and cannot be edited.", status=400)
        if role not in dict(Roles.CURRENT_CHOICES):
            return error_response("Unknown or non-assignable role.", status=404)
        return None

    def post(self, request, role):
        invalid = self._validate_role(role)
        if invalid:
            return invalid
        serializer = RolePermissionAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)

        permission = Permission.objects.get(code=serializer.validated_data["permission_code"])
        _, created = RolePermission.objects.get_or_create(legacy_role_code=role, permission=permission)

        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.PERMISSION_CHANGE,
                         "accounts.RolePermission", role, user=request.user,
                         metadata={"action": "granted", "role": role, "permission_code": permission.code})

        return success_response(
            {"role": role, "permission_code": permission.code, "already_granted": not created},
            message="Permission granted." if created else "Permission was already granted.",
        )

    def delete(self, request, role):
        invalid = self._validate_role(role)
        if invalid:
            return invalid
        serializer = RolePermissionAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)

        permission = Permission.objects.get(code=serializer.validated_data["permission_code"])
        deleted, _ = RolePermission.objects.filter(legacy_role_code=role, permission=permission).delete()

        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.PERMISSION_CHANGE,
                         "accounts.RolePermission", role, user=request.user,
                         metadata={"action": "revoked", "role": role, "permission_code": permission.code})

        return success_response(
            {"role": role, "permission_code": permission.code, "was_granted": bool(deleted)},
            message="Permission revoked." if deleted else "Role did not have this permission.",
        )
