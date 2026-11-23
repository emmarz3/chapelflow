from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from urllib.parse import urlencode


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_email_verification(self, email, token):
    """Deliver a short-lived, single-purpose email verification link."""
    query = urlencode({"token": token})
    verify_link = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?{query}"
    try:
        send_mail(
            subject="Confirm your ChapelFlow email address",
            message=(
                "Welcome to ChapelFlow. Confirm your email address by opening this link:\n\n"
                f"{verify_link}\n\n"
                "This link expires in 30 minutes. If you did not create this account, you can ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=(
                "<p>Welcome to ChapelFlow.</p>"
                "<p>Confirm your email address to activate sign-in for your account.</p>"
                f'<p><a href="{verify_link}">Verify email address</a></p>'
                "<p>This link expires in 30 minutes. If you did not create this account, you can ignore this email.</p>"
            ),
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_password_reset_email(self, user_id, uid, token):
    from .models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    reset_link = f"{getattr(settings, 'FRONTEND_URL', 'https://app.chapelflow.example')}/reset-password/{uid}/{token}/"
    try:
        send_mail(
            subject="ChapelFlow Password Reset",
            message=f"Use the link below to reset your password:\n\n{reset_link}\n\nThis link expires soon.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)
