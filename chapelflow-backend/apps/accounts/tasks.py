from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from urllib.parse import quote


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_registration_verification_email(self, user_id, token):
    user = get_user_model().objects.filter(pk=user_id, is_active=False).first()
    if not user or not user.email:
        return
    link = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={quote(token)}"
    try:
        send_mail("Verify your ChapelFlow email", f"Open this link within 24 hours to verify your account:\n\n{link}", settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except Exception as exc:
        raise self.retry(exc=exc)
