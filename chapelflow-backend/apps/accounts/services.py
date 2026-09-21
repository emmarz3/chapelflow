import logging

from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import LoginHistory, User

security_logger = logging.getLogger("chapelflow.security")


def record_login(user, request, successful: bool, failure_reason: str = "", identifier_attempted: str = ""):
    ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR"))
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    LoginHistory.objects.create(
        user=user if (user is not None and getattr(user, "pk", None)) else None,
        identifier_attempted="" if (user and getattr(user, "pk", None)) else identifier_attempted,
        ip_address=ip,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        successful=successful,
        failure_reason=failure_reason,
    )
    if successful:
        user.last_login_ip = ip
        user.save(update_fields=["last_login_ip"])
        security_logger.info("login_success user_id=%s role=%s", user.id, user.role)
        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(AuditAction.LOGIN, "accounts.User", user.id, user=user)
    else:
        security_logger.warning("login_failed identifier=%s reason=%s", identifier_attempted or user, failure_reason)


def generate_password_reset_token(user: User):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return uid, token


def user_requires_mfa(user: User) -> bool:
    from django.conf import settings
    return user.role in getattr(settings, "MFA_ENFORCED_ROLES", [])


def list_active_sessions(user: User):
    """
    Active sessions == unexpired, non-blacklisted refresh tokens
    (rest_framework_simplejwt.token_blacklist.OutstandingToken) issued to
    this user. A refresh token is the practical definition of "a logged
    in device" here since access tokens are short-lived and stateless.
    """
    from django.utils import timezone
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    blacklisted_ids = BlacklistedToken.objects.filter(token__user=user).values_list("token_id", flat=True)
    return (
        OutstandingToken.objects.filter(user=user, expires_at__gt=timezone.now())
        .exclude(id__in=blacklisted_ids)
        .order_by("-created_at")
    )


def revoke_session(user: User, jti: str) -> bool:
    """Blacklist a single outstanding token by jti, scoped to `user` so a
    user can never revoke someone else's session by guessing a jti."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    token = OutstandingToken.objects.filter(user=user, jti=jti).first()
    if not token:
        return False
    BlacklistedToken.objects.get_or_create(token=token)
    return True


def revoke_all_sessions(user: User, except_jti: str = None) -> int:
    """Blacklist every outstanding, non-expired token for `user`, optionally
    keeping the current session (except_jti) alive. Returns count revoked."""
    count = 0
    for token in list_active_sessions(user):
        if except_jti and token.jti == except_jti:
            continue
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        BlacklistedToken.objects.get_or_create(token=token)
        count += 1
    return count
