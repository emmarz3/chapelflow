"""
Phase 10: delivery-confirmation webhook handling. Mirrors the pattern
already established in apps.finance.services (PaymentService/
verify_webhook_signature/process_webhook) — same shape, same
idempotency posture, applied to notification delivery instead of
payment status.
"""
import hashlib
import hmac
import json
import logging
<<<<<<< HEAD
from uuid import UUID

from django.conf import settings
from django.db import transaction
=======

from django.conf import settings
>>>>>>> origin/main

from .models import Notification, NotificationStatus

notifications_logger = logging.getLogger("chapelflow.notifications")


class WebhookVerificationError(Exception):
    pass


def verify_signature(request) -> bool:
    """
    Generic HMAC-SHA256 signature check against a shared secret, the same
    posture as PaystackService.verify_webhook_signature. Real providers
    each have their own header/algorithm; when a specific SMS/push
    provider is wired up for real, add a provider-specific check here
    the same way apps.finance.services adds one PaymentService subclass
    per gateway. An empty secret always fails closed (never treated as
    "no verification needed").
    """
    secret = getattr(settings, "NOTIFICATION_WEBHOOK_SECRET", "") or ""
    if not secret:
        return False
    signature = request.headers.get("X-Webhook-Signature", "")
    computed = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, computed)


def process_delivery_webhook(request) -> dict:
    """
    Verifies the webhook, then idempotently applies a SENT -> DELIVERED
    transition. Payload shape: {"notification_id": "...", "event": "delivered"|"failed", ...}.
    Re-delivery of the same event (providers routinely retry webhooks) is
    a safe no-op: mark_notification_delivered only ever updates a row
    still in SENT, so a second call against an already-DELIVERED
    notification changes nothing.
    """
    if not verify_signature(request):
        notifications_logger.warning("notification_webhook_signature_invalid")
        raise WebhookVerificationError("Invalid webhook signature.")

    try:
        payload = json.loads(request.body)
    except (ValueError, TypeError):
        raise WebhookVerificationError("Malformed JSON payload.")

<<<<<<< HEAD
    if not isinstance(payload, dict):
        raise WebhookVerificationError("Webhook payload must be an object.")
=======
>>>>>>> origin/main
    notification_id = payload.get("notification_id")
    event = payload.get("event")
    if not notification_id:
        raise WebhookVerificationError("Webhook payload missing notification_id.")
<<<<<<< HEAD
    try:
        notification_id = UUID(str(notification_id))
    except (TypeError, ValueError, AttributeError):
        raise WebhookVerificationError("Invalid notification_id.")
    if event not in {"delivered", "failed"}:
        raise WebhookVerificationError("Unsupported delivery event.")

    with transaction.atomic():
        notification = Notification.objects.select_for_update().filter(id=notification_id).first()
        if notification is None:
            notifications_logger.warning("notification_webhook_unknown_id id=%s", notification_id)
            raise WebhookVerificationError("No matching notification for this id.")

        if event == "delivered":
            if notification.status == NotificationStatus.SENT:
                notification.status = NotificationStatus.DELIVERED
                notification.provider_response = {**(notification.provider_response or {}), "delivered": True, **payload}
                notification.save(update_fields=["status", "provider_response"])
            else:
                notifications_logger.info(
                    "notification_webhook_idempotent_skip id=%s status=%s", notification_id, notification.status
                )
        elif notification.status in (NotificationStatus.SENT, NotificationStatus.PENDING):
=======

    notification = Notification.objects.filter(id=notification_id).first()
    if notification is None:
        notifications_logger.warning("notification_webhook_unknown_id id=%s", notification_id)
        raise WebhookVerificationError("No matching notification for this id.")

    if event == "delivered":
        if notification.status == NotificationStatus.SENT:
            notification.status = NotificationStatus.DELIVERED
            notification.provider_response = {**(notification.provider_response or {}), "delivered": True, **payload}
            notification.save(update_fields=["status", "provider_response"])
        else:
            notifications_logger.info(
                "notification_webhook_idempotent_skip id=%s status=%s", notification_id, notification.status
            )
    elif event == "failed":
        if notification.status in (NotificationStatus.SENT, NotificationStatus.PENDING):
>>>>>>> origin/main
            notification.status = NotificationStatus.FAILED
            notification.provider_response = {**(notification.provider_response or {}), **payload}
            notification.save(update_fields=["status", "provider_response"])

<<<<<<< HEAD
        return {"notification_id": str(notification.id), "status": notification.status}
=======
    return {"notification_id": str(notification.id), "status": notification.status}
>>>>>>> origin/main
