"""
Project-specific deployment-readiness checks (Phase 1).

Run via `python manage.py check --deploy` -- deliberately registered
with `deploy=True` so these never fire on a plain `manage.py check`
(the command developers/CI run constantly) and only run when someone
is explicitly validating a deployment, exactly like Django's own
built-in equivalents (django.core.checks.security.base) already
behave for SECRET_KEY/DEBUG/ALLOWED_HOSTS.

Deliberately NOT reimplemented here because Django already checks them
under --deploy: SECRET_KEY strength (check_secret_key), DEBUG being off
(check_debug), ALLOWED_HOSTS being non-empty (check_allowed_hosts),
HSTS/XFrame/SSL-redirect/security-middleware presence. This module only
adds checks for settings that are specific to ChapelFlow and that
Django has no way to know about: which storage/payment/SMS provider is
selected, and whether the matching credentials are actually present.

All findings are Warnings, not Errors, matching Django's own severity
convention for --deploy checks -- these describe a degraded-but-running
state (e.g. uploads will fail, payments/SMS stay stubbed), not a guaranteed
crash. A pipeline that wants these to block a release can already do
that with `manage.py check --deploy --fail-level WARNING`.
"""
from django.conf import settings
from django.core.checks import Tags, Warning, register

DEV_DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


@register(Tags.security, deploy=True)
def check_allowed_hosts_not_default(app_configs, **kwargs):
    """
    Django's own check_allowed_hosts only verifies ALLOWED_HOSTS is
    non-empty -- it would happily pass with the dev-example value still
    in place, since that list isn't empty. This catches the more
    specific "still the .env.example placeholder" case.
    """
    if list(settings.ALLOWED_HOSTS) == DEV_DEFAULT_ALLOWED_HOSTS:
        return [
            Warning(
                "ALLOWED_HOSTS is still the development default "
                f"({DEV_DEFAULT_ALLOWED_HOSTS!r}). Set it to the real "
                "production host name(s) before serving traffic.",
                id="chapelflow.W001",
            )
        ]
    return []


@register(Tags.security, deploy=True)
def check_storage_provider_credentials(app_configs, **kwargs):
    """STORAGE_PROVIDER selects an upload backend; its credentials must actually be set."""
    provider = settings.STORAGE_PROVIDER
    warnings = []

    if provider == "cloudinary":
        missing = [
            name for name in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
            if not getattr(settings, name, "")
        ]
        if missing:
            warnings.append(
                Warning(
                    f"STORAGE_PROVIDER is 'cloudinary' but {', '.join(missing)} "
                    "is not set. File uploads will fail at runtime.",
                    id="chapelflow.W002",
                )
            )
    elif provider == "s3":
        missing = [
            name for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_STORAGE_BUCKET_NAME")
            if not getattr(settings, name, "")
        ]
        if missing:
            warnings.append(
                Warning(
                    f"STORAGE_PROVIDER is 's3' but {', '.join(missing)} is not "
                    "set. File uploads will fail at runtime.",
                    id="chapelflow.W002",
                )
            )
    elif provider == "local":
        warnings.append(
            Warning(
                "STORAGE_PROVIDER is 'local' -- files are written to the "
                "container's local disk, which will NOT persist across "
                "deploys/restarts and won't be shared across multiple web "
                "workers. Fine for development only.",
                id="chapelflow.W003",
            )
        )

    return warnings


@register(Tags.security, deploy=True)
def check_email_configured(app_configs, **kwargs):
    """production.py hardcodes the SMTP email backend; EMAIL_HOST must actually be set."""
    if not settings.EMAIL_HOST:
        return [
            Warning(
                "EMAIL_HOST is not set. The SMTP email backend is active "
                "in production settings, so verification emails, password "
                "resets, and notification emails will fail to send.",
                id="chapelflow.W004",
            )
        ]
    return []


@register(Tags.security, deploy=True)
def check_payment_provider_configured(app_configs, **kwargs):
    """At least one payment gateway secret should be configured for Giving/Pledges to process real payments."""
    if not settings.PAYSTACK_SECRET_KEY and not settings.FLUTTERWAVE_SECRET_KEY:
        return [
            Warning(
                "Neither PAYSTACK_SECRET_KEY nor FLUTTERWAVE_SECRET_KEY is "
                "set. Online giving/payment webhooks have no live provider "
                "to verify against.",
                id="chapelflow.W005",
            )
        ]
    return []


@register(Tags.security, deploy=True)
def check_sms_provider_configured(app_configs, **kwargs):
    """
    Informational only: Phase 0 already made the notification system
    honest about this (NotificationStatus.STUBBED instead of a fake
    SENT), so a missing SMS_API_KEY is not a bug -- just worth
    surfacing explicitly at deploy-check time.
    """
    if not settings.SMS_API_KEY:
        return [
            Warning(
                "SMS_API_KEY is not set. SMS notifications will be "
                "recorded as STUBBED rather than actually sent "
                "(see apps.notifications) until a real provider key is added.",
                id="chapelflow.W006",
            )
        ]
    return []
