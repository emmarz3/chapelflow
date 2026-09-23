from celery import shared_task


@shared_task
def send_pending_follow_up_reminders():
    """
    Spec Phase 5: New visitor -> Follow-up task -> Assignment -> Reminder
    -> Completion, "use Celery for scheduled reminders". Runs on a
    periodic beat schedule (see config/celery.py) rather than being
    triggered per-object, since a reminder is inherently time-based
    ("this is due/overdue now"), not event-based.

    Only ever creates a real apps.notifications.Notification and lets the
    existing provider abstraction (deliver_notification) decide SENT vs
    STUBBED — this task never fabricates a "reminder sent" outcome itself.
    Idempotent per run: a follow-up is only ever reminded about once
    (reminded_at is stamped immediately, inside the same transaction that
    reads it), so overlapping/duplicate beat ticks can't double-send.
    """
    from django.db import transaction
    from django.utils import timezone

    from .models import VisitorFollowUp

    due = VisitorFollowUp.objects.select_for_update(skip_locked=True).filter(
        outcome=VisitorFollowUp.Outcome.PENDING,
        scheduled_for__lte=timezone.now(),
        completed_at__isnull=True,
        reminder_sent_at__isnull=True,
        assigned_to__isnull=False,
    ).select_related("assigned_to", "visitor")

    sent = 0
    with transaction.atomic():
        for follow_up in due:
            follow_up.reminder_sent_at = timezone.now()
            follow_up.save(update_fields=["reminder_sent_at"])

            from apps.notifications.models import Notification
            from apps.notifications.tasks import deliver_notification

            notification = Notification.objects.create(
                recipient=follow_up.assigned_to,
                title="Follow-up reminder",
                body=f"Your follow-up with {follow_up.visitor.full_name} was due and is still pending.",
                channel="EMAIL",
            )
            deliver_notification.delay(str(notification.id))
            sent += 1

    return {"reminders_sent": sent}
