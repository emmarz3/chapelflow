from django.contrib.auth import get_user_model
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.core.signing import BadSignature, SignatureExpired
from django.db.models import Q
from django.utils import timezone
import secrets
from http.cookies import Morsel
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from common.constants.roles import Roles
from common.permissions.rbac import IsChapelAdminOrSuperAdmin, IsSuperAdmin, user_has_completed_required_mfa
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
    LocalSuperAdminSetupSerializer,
    StudentSelfProfileSerializer,
    UserPublicSerializer,
)
from .services import (
    list_active_sessions,
    record_login,
    revoke_all_sessions,
    revoke_session,
)

User = get_user_model()
INSTITUTIONAL_ROLES = (
    "CHAPLAIN", "STUDENT_CHAPLAIN", "ASSISTANT_STUDENT_CHAPLAIN",
    "UNIT_HEAD", "FELLOWSHIP_LEADER", "HOSTEL_COORDINATOR", "ATTENDANCE_USHER",
)


ACCESS_COOKIE = "chapelflow_access"
REFRESH_COOKIE = "chapelflow_refresh"
CSRF_COOKIE = "chapelflow_csrf"


def _auth_cookie_options():
    secure = not settings.DEBUG or _use_partitioned_local_cookies()
    return {
        "secure": secure,
        "samesite": "None" if secure else "Lax",
    }


def _use_partitioned_local_cookies():
    return (
        settings.DEBUG
        and getattr(settings, "CHAPELFLOW_LOCAL_EMBEDDED_PREVIEW", False)
        and "partitioned" in Morsel._reserved
    )


def _partitioned_cookies_enabled():
    return bool(
        getattr(settings, "CHAPELFLOW_PARTITIONED_COOKIES", False)
        or _use_partitioned_local_cookies()
    )


def _mark_partitioned_local_cookies(response):
    if _partitioned_cookies_enabled():
        # Python 3.12's http.cookies.Morsel does not register the CHIPS
        # attribute by default. Register it so Set-Cookie emits Partitioned.
        if "partitioned" not in Morsel._reserved:
            Morsel._reserved["partitioned"] = "Partitioned"
        if "partitioned" not in Morsel._flags:
            Morsel._flags.add("partitioned")
        for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
            if name in response.cookies:
                response.cookies[name]["partitioned"] = True
    return response


def _set_auth_cookies(response, access, refresh):
    """Keep auth credentials HttpOnly and issue a JS-readable CSRF token."""
    cookie_options = _auth_cookie_options()
    common = {"httponly": True, "path": "/", **cookie_options}
    response.set_cookie(ACCESS_COOKIE, access, max_age=15 * 60, **common)
    response.set_cookie(REFRESH_COOKIE, refresh, max_age=7 * 24 * 60 * 60, **common)
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        CSRF_COOKIE, csrf_token, max_age=7 * 24 * 60 * 60,
        httponly=False, path="/", **cookie_options,
    )
    # The SPA is hosted on a different Render origin and cannot read this
    # API host's cookie. Returning the CSRF value in the JSON envelope lets
    # it send the matching double-submit header without exposing auth tokens.
    payload = getattr(response, "data", None)
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        payload["data"]["csrf_token"] = csrf_token
    return _mark_partitioned_local_cookies(response)


def _clear_auth_cookies(response):
    cookie_options = _auth_cookie_options()
    response.delete_cookie(ACCESS_COOKIE, path="/", samesite=cookie_options["samesite"])
    response.delete_cookie(REFRESH_COOKIE, path="/", samesite=cookie_options["samesite"])
    response.delete_cookie(CSRF_COOKIE, path="/", samesite=cookie_options["samesite"])
    return _mark_partitioned_local_cookies(response)


class CsrfTokenView(APIView):
    """Bootstrap the CSRF double-submit token for the cross-origin SPA."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.COOKIES.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
        response = success_response({"csrf_token": token})
        response.set_cookie(
            CSRF_COOKIE,
            token,
            max_age=7 * 24 * 60 * 60,
            httponly=False,
            path="/",
            **_auth_cookie_options(),
        )
        response["Cache-Control"] = "no-store"
        return _mark_partitioned_local_cookies(response)


class RegistrationAvailabilityView(APIView):
    """Early duplicate-account check for the multi-step public registration form."""
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration_check"

    def post(self, request):
        email = str(request.data.get("email") or "").strip()
        matric_no = str(request.data.get("matric_no") or "").strip()
        if not email and not matric_no:
            return error_response("Enter an email address or matriculation number to check.", status=400)

        result = {}
        if email:
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                validate_email(email)
            except DjangoValidationError:
                return error_response("Enter a valid email address.", {"email": ["Enter a valid email address."]}, status=400)
            result["email_available"] = not User.objects.filter(email__iexact=email).exists()
        if matric_no:
            from .validators import normalize_matric_no
            normalized = normalize_matric_no(matric_no)
            result["matric_no_available"] = not User.objects.filter(matric_no=normalized).exists()

        return success_response(result)


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
        from .tasks import send_email_verification

        verification_token = signing.dumps(
            {"user_id": str(user.pk), "email": user.email},
            salt="chapelflow.email-verification",
            compress=True,
        )
        send_email_verification.delay(user.email, verification_token)
        return success_response(
            {
                "verification_required": True,
                "approval_required": False,
                "email": user.email,
                "user": UserPublicSerializer(user).data,
            },
            message="Registration successful. Check your email to verify your account.",
            status=201,
        )


class EmailVerificationView(APIView):
    """Confirm a newly registered account using a signed, time-limited token."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verification"

    def post(self, request):
        token = str(request.data.get("token") or "").strip()
        if not token:
            return error_response("A verification token is required.", status=400)
        try:
            payload = signing.loads(
                token,
                salt="chapelflow.email-verification",
                max_age=settings.EMAIL_VERIFICATION_TIMEOUT_SECONDS,
            )
            if not isinstance(payload, dict):
                raise BadSignature("Invalid verification payload.")
            user = User.objects.filter(
                pk=payload.get("user_id"),
                email__iexact=payload.get("email", ""),
            ).first()
        except (BadSignature, SignatureExpired, TypeError, ValueError):
            user = None
        if not user or not user.email:
            return error_response("This verification link is invalid or has expired.", status=400)
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        return success_response({"verified": True}, message="Email address verified successfully.")


class EmailVerificationResendView(APIView):
    """Resend confirmation without revealing whether an email has an account."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_verification"

    def post(self, request):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.core.validators import validate_email

        email = str(request.data.get("email") or "").strip()
        try:
            validate_email(email)
        except DjangoValidationError:
            return error_response("Enter a valid email address.", {"email": ["Enter a valid email address."]}, status=400)

        user = User.objects.filter(email__iexact=email, email_verified=False).first()
        if user:
            token = signing.dumps(
                {"user_id": str(user.pk), "email": user.email},
                salt="chapelflow.email-verification",
                compress=True,
            )
            from .tasks import send_email_verification
            send_email_verification.delay(user.email, token)

        return success_response(
            {"sent": True},
            message="If that address has an unverified ChapelFlow account, a fresh confirmation link has been sent.",
        )


class LocalSuperAdminSetupView(APIView):
    """Create and sign in the first Super Admin in local development only."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        if not settings.DEBUG:
            return error_response("Not found.", status=404)

        serializer = LocalSuperAdminSetupSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)

        with transaction.atomic():
            from .models import InstitutionalAccountControl

            control, _ = InstitutionalAccountControl.objects.get_or_create(singleton=1)
            InstitutionalAccountControl.objects.select_for_update().get(pk=control.pk)
            if User.objects.filter(role=Roles.SUPER_ADMIN).exists():
                return error_response(
                    "Super Admin setup is already complete. Sign in with the existing account.",
                    status=409,
                )
            if User.objects.filter(email__iexact=serializer.validated_data["email"]).exists():
                return error_response("That email address is already in use.", status=400)
            user = User.objects.create_superuser(**serializer.validated_data)

        tokens = RefreshToken.for_user(user)
        response = success_response(
            {
                "access": str(tokens.access_token),
                "refresh": str(tokens),
                "user": UserPublicSerializer(user).data,
            },
            message="Super Admin created and signed in.",
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

        if user.mfa_enabled and not _verify_otp(user, serializer.validated_data.get("otp", "")):
            record_login(user, request, successful=False, failure_reason="invalid_otp")
            return error_response("Enter a valid authenticator code to sign in.", {"otp": ["The code is missing or invalid."]}, status=400)

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

    Reopening an unconfirmed enrollment returns its existing secret so a
    session expiry does not invalidate the authenticator the user just added.
    Re-enrolling a confirmed device rotates the secret and resets confirmation.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import pyotp

        from .models import MFADevice

        device, created = MFADevice.objects.get_or_create(
            user=request.user, defaults={"secret": pyotp.random_base32(), "confirmed": False},
        )
        if not created and device.confirmed:
            device.secret = pyotp.random_base32()
            device.confirmed = False
            device.save(update_fields=["secret", "confirmed"])

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
        # Browser cookie refreshes are cross-site on separate *.onrender.com
        # hosts, so require the matching double-submit token as well.
        if not request.data.get("refresh"):
            csrf_cookie = request.COOKIES.get(CSRF_COOKIE, "")
            csrf_header = request.headers.get("X-ChapelFlow-CSRF", "")
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return error_response("CSRF verification failed.", status=403)
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
            response = error_response("Refresh token is required.", status=400)
            return _clear_auth_cookies(response)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            response = error_response("Invalid or already-invalidated token.", status=400)
            return _clear_auth_cookies(response)
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.LOGOUT, "accounts.User", request.user.id, user=request.user)
        return _clear_auth_cookies(success_response(message="Logged out successfully."))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(UserPublicSerializer(request.user).data)


class AdminAccountDirectoryView(APIView):
    """Paginated account inventory; credentials and password hashes never leave the server."""
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        try:
            page = max(1, int(request.query_params.get("page", "1")))
        except ValueError:
            return error_response("Enter a valid page number.", status=400)
        page_size = 25
        accounts = User.objects.select_related("branch", "role_obj").order_by("-date_joined", "-id")
        search = request.query_params.get("search", "").strip()[:150]
        if search:
            accounts = accounts.filter(
                Q(email__icontains=search) | Q(matric_no__icontains=search)
                | Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )
        count = accounts.count()
        accounts = accounts[(page - 1) * page_size:page * page_size]
        response = success_response({
            "items": [{
                "id": str(account.id),
                "name": f"{account.first_name} {account.last_name}".strip(),
                "email": account.email or "",
                "matric_no": account.matric_no or "",
                "role": account.get_role_code(),
                "branch_name": account.branch.name if account.branch else "",
                "is_active": account.is_active,
                "deleted_at": account.deleted_at,
                "date_joined": account.date_joined,
                "can_reset": account.get_role_code() != Roles.SUPER_ADMIN and account.deleted_at is None,
            } for account in accounts],
            "page": page,
            "page_size": page_size,
            "count": count,
        })
        response["Cache-Control"] = "no-store"
        return response


class AdminAccountPasswordResetView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        account = User.objects.exclude(role=Roles.SUPER_ADMIN).filter(pk=pk, deleted_at__isnull=True).first()
        if not account or account.get_role_code() == Roles.SUPER_ADMIN:
            return error_response("Account not found or cannot be reset here.", status=404)
        return _issue_temporary_password(request, account)


def _confirm_sensitive_admin_action(request):
    """Fresh password and authenticator proof, independent of a live session."""
    import pyotp
    from .models import MFADevice

    password = request.data.get("password", "")
    otp = request.data.get("otp", "")
    device = MFADevice.objects.filter(user=request.user, confirmed=True).first()
    if not (request.user.is_active and user_has_completed_required_mfa(request.user)
            and device and isinstance(password, str) and request.user.check_password(password)
            and isinstance(otp, str) and pyotp.TOTP(device.secret).verify(otp, valid_window=1)):
        return error_response("Confirm your current password and authenticator code.", status=403)
    return None


class AdminAccountEraseView(APIView):
    """Erase a non-admin account and its linked member profile, with reauthentication."""
    permission_classes = [IsSuperAdmin]
    throttle_scope = "admin_destructive"

    def post(self, request, pk):
        from django.db.models.deletion import ProtectedError
        from apps.attendance.models import AttendanceCheckpoint
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        from apps.members.models import Member
        from apps.social.models import SocialComment, SocialPost

        failure = _confirm_sensitive_admin_action(request)
        if failure:
            return failure
        target = User.objects.filter(pk=pk).first()
        if not target or target.get_role_code() == Roles.SUPER_ADMIN:
            return error_response("Account not found or protected.", status=404)
        identifier = target.email or target.matric_no
        if request.data.get("confirmation") != identifier:
            return error_response("Type the account's email or matric number to confirm.", status=400)
        try:
            with transaction.atomic():
                # Checkpoints protect their usher FK. Remove those rows before
                # deleting the user; other attendance remains without a member.
                AttendanceCheckpoint.objects.filter(usher=target).delete()
                SocialComment.objects.filter(author=target).delete()
                SocialPost.objects.filter(author=target).delete()
                Member.objects.filter(user=target).delete()
                target_id = target.pk
                target.delete()
                write_audit_log(AuditAction.DELETE, "accounts.User", target_id, user=request.user,
                                metadata={"erased_account_and_member": True})
        except ProtectedError:
            return error_response("This account has protected records. No data was deleted.", status=409)
        return success_response(message="Account, member profile and Upper Room posts deleted. Financial, audit, and shared public records remain.")


class AdminDataResetView(APIView):
    """Preview and explicitly execute a full database fresh start."""
    permission_classes = [IsSuperAdmin]
    throttle_scope = "admin_destructive"

    def get(self, request):
        from .data_reset import reset_preview
        from .models import MFADevice
        if (not request.user.is_active or not user_has_completed_required_mfa(request.user)
                or not MFADevice.objects.filter(user=request.user, confirmed=True).exists()):
            return error_response("Complete Super Admin MFA before resetting data.", status=403)
        return success_response(reset_preview(request.user))

    def post(self, request):
        from .data_reset import RESET_PHRASE, reset_database
        failure = _confirm_sensitive_admin_action(request)
        if failure:
            return failure
        if request.data.get("confirmation") != RESET_PHRASE:
            return error_response(f"Type {RESET_PHRASE} exactly in the confirmation phrase field.", status=400)
        if request.data.get("backup_acknowledged") is not True:
            return error_response("Acknowledge that you verified a restorable database backup.", status=400)
        token = request.data.get("token")
        if not isinstance(token, str):
            return error_response("Review the current data before resetting.", status=400)
        try:
            reset_database(request.user, token)
        except SignatureExpired:
            return error_response(
                "The reset preview expired after five minutes. Review the current records to generate a new preview.",
                status=409,
            )
        except (BadSignature, ValueError):
            return error_response(
                "Application records changed after this preview. Review the current records to generate a new preview.",
                status=409,
            )
        return _clear_auth_cookies(success_response(message="Database reset. Sign in again with your Super Admin account."))


class InstitutionalAccountListCreateView(APIView):
    """Super-admin control plane for chapel staff accounts, never public users."""
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        accounts = User.objects.exclude(role=Roles.SUPER_ADMIN).filter(deleted_at__isnull=True,
            role__in=INSTITUTIONAL_ROLES
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
        account = User.objects.exclude(role=Roles.SUPER_ADMIN).filter(deleted_at__isnull=True,
            pk=pk, role__in=INSTITUTIONAL_ROLES,
        ).first()
        return account if account and account.get_role_code() != Roles.SUPER_ADMIN else None

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

    def delete(self, request, pk):
        account = self._account(pk)
        if not account:
            return error_response("Institutional account not found.", status=404)
        with transaction.atomic():
            account.is_active = False
            account.deleted_at = timezone.now()
            account.set_unusable_password()
            account.save(update_fields=["is_active", "deleted_at", "password"])
            revoke_all_sessions(account)
            from apps.audit.models import AuditAction
            from apps.audit.services import write_audit_log
            write_audit_log(AuditAction.DELETE, "accounts.User", account.id, user=request.user,
                            metadata={"institutional_account": True, "access_revoked": True})
        return success_response(message="Institutional account removed. Historical records are retained.")


class InstitutionalAccountPasswordResetView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        account = User.objects.filter(pk=pk, role__in=INSTITUTIONAL_ROLES, deleted_at__isnull=True).first()
        if not account:
            return error_response("Institutional account not found.", status=404)
        return _issue_temporary_password(request, account)


def _issue_temporary_password(request, account):
    # Existing passwords are irretrievable. Return the replacement once, never log it.
    uppercase = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    lowercase = "abcdefghijkmnopqrstuvwxyz"
    digits = "23456789"
    symbols = "!@#$%"
    alphabet = uppercase + lowercase + digits + symbols
    characters = [
        secrets.choice(uppercase), secrets.choice(lowercase),
        secrets.choice(digits), secrets.choice(symbols),
        *(secrets.choice(alphabet) for _ in range(14)),
    ]
    secrets.SystemRandom().shuffle(characters)
    temporary_password = "".join(characters)
    with transaction.atomic():
        account.set_password(temporary_password)
        account.password_change_required = True
        account.save(update_fields=["password", "password_change_required"])
        revoke_all_sessions(account)
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(AuditAction.PASSWORD_CHANGE, "accounts.User", account.id, user=request.user,
                        metadata={"initiated_by_admin": True, "temporary_password_issued": True})
    response = success_response(
        {"temporary_password": temporary_password, "password_change_required": True},
        message="Temporary password issued. It will not be shown again.",
    )
    response["Cache-Control"] = "no-store"
    return response


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return error_response("Validation failed.", serializer.errors, status=400)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.password_change_required = False
        request.user.save(update_fields=["password", "password_change_required"])
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
        from rest_framework_simplejwt.tokens import RefreshToken
        active_tokens = OutstandingToken.objects.filter(user=request.user).exclude(
            id__in=BlacklistedToken.objects.values_list("token_id", flat=True)
        )
        for outstanding in active_tokens.iterator(chunk_size=500):
            RefreshToken(outstanding.token).blacklist()
        from apps.audit.models import AuditAction
        from apps.audit.services import write_audit_log
        write_audit_log(
            AuditAction.PASSWORD_CHANGE,
            "accounts.User",
            request.user.id,
            user=request.user,
            metadata={"completed_required_change": True},
        )
        return success_response(message="Password changed successfully.")


class StudentProfileView(APIView):
    """Self-service profile endpoint; academic fields remain read-only."""
    permission_classes = [IsAuthenticated]

    def _member(self, request):
        if request.user.get_role_code() != Roles.MEMBER:
            return None
        from apps.members.models import Member
        return Member.objects.filter(user=request.user).select_related("department").first()

    def get(self, request):
        member = self._member(request)
        data = {
            "email": request.user.email or "",
            "phone_number": request.user.phone_number or "",
            "bio": request.user.bio or "",
            "photo_url": request.user.photo_url or "",
            "role": request.user.get_role_code(),
            "address": member.address if member else "",
            "date_of_birth": member.date_of_birth.isoformat() if member and member.date_of_birth else None,
            "emergency_contact_name": member.emergency_contact_name if member else "",
            "emergency_contact_phone": member.emergency_contact_phone if member else "",
            "matric_no": request.user.matric_no if member else None,
            "department": getattr(member.department, "name", None) if member else None,
        }
        return success_response(data)

    def patch(self, request):
        member = self._member(request)
        serializer = StudentSelfProfileSerializer(data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        member_fields = {"address", "date_of_birth", "emergency_contact_name", "emergency_contact_phone"}
        if member is None and member_fields.intersection(data):
            return error_response("Contact and academic details are available only to member accounts.", status=403)

        with transaction.atomic():
            user_fields = [field for field in ("email", "phone_number", "bio") if field in data]
            for field in user_fields:
                setattr(request.user, field, data[field])
            if user_fields:
                request.user.save(update_fields=user_fields)

            if member is not None:
                changed_member_fields = [field for field in member_fields if field in data]
                for field in changed_member_fields:
                    setattr(member, field, data[field])
                if "email" in data:
                    member.email = data["email"]
                    changed_member_fields.append("email")
                if "phone_number" in data:
                    member.phone_number = data["phone_number"]
                    changed_member_fields.append("phone_number")
                if changed_member_fields:
                    member.save(update_fields=list(set(changed_member_fields)))

        return self.get(request)


class ProfilePhotoUploadView(APIView):
    """Stores the authenticated account's image, for every role."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        from apps.members.models import Member
        member = Member.objects.filter(user=request.user).first()
        file_obj = request.FILES.get("file")
        if not file_obj:
            return error_response("Choose an image to upload.", status=400)
        extension = file_obj.name.rsplit(".", 1)[-1].lower() if "." in file_obj.name else ""
        if extension not in {"jpg", "jpeg", "png", "webp", "gif"} or not (file_obj.content_type or "").startswith("image/"):
            return error_response("Profile photos must be JPG, PNG, WebP, or GIF images.", status=400)

        from django.core.exceptions import ValidationError
        from apps.uploads.models import Upload, UploadCategory
        from apps.uploads.storage import generate_storage_filename, get_storage_service
        from apps.uploads.validators import validate_upload, validate_category_content

        try:
            validate_upload(file_obj, max_size_mb=10)
            validate_category_content(file_obj, UploadCategory.MEMBER_PHOTO)
        except ValidationError as exc:
            return error_response(str(exc), status=400)
        try:
            file_url = get_storage_service().upload_bytes(
                file_obj.read(),
                generate_storage_filename(file_obj.name, prefix="member-photo"),
                content_type=file_obj.content_type,
            )
        except Exception:
            return error_response("Photo storage is unavailable. Please try again shortly.", status=503)
        with transaction.atomic():
            Upload.objects.create(
                branch=request.user.branch,
                uploaded_by=request.user,
                category=UploadCategory.MEMBER_PHOTO,
                original_filename=file_obj.name,
                file_url=file_url,
                content_type=file_obj.content_type or "",
                size_bytes=file_obj.size,
            )
            request.user.photo_url = file_url
            request.user.save(update_fields=["photo_url"])
            if member is not None:
                member.photo_url = file_url
                member.save(update_fields=["photo_url", "updated_at"])
        return success_response({"photo_url": file_url})


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Account recovery is administrator-assisted. Keep the response
        # identical for every address so this endpoint cannot enumerate users.
        return success_response(
            message="Contact the ChapelFlow Super Admin to receive a temporary password."
        )


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
        user.password_change_required = False
        user.save(update_fields=["password", "password_change_required"])

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
