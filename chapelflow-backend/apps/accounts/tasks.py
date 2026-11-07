from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


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
