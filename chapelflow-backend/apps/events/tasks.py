from celery import shared_task


@shared_task
def send_due_event_reminders():
    """
    Spec Phase 7: "Event -> Reminder schedule -> Celery -> Notification.
    Never fake notification delivery." Runs periodically (see
    config/celery.py beat schedule). For every due, unsent EventReminder,
    fans out a real apps.notifications.Notification to every CONFIRMED
    registrant on that occurrence and lets the existing provider
    abstraction decide SENT vs STUBBED -- this task never marks anything
    "sent" itself beyond "a Notification was created and handed to
    deliver_notification".

    Idempotent: `sent=True` is stamped in the same pass a reminder is
    picked up, before any Notification is created, so a slow run
    overlapping with the next beat tick can't double up.
    """
    from django.db import transaction
    from django.utils import timezone

    from .models import EventReminder, EventRegistrationStatus

    due = EventReminder.objects.select_for_update(skip_locked=True).filter(
        sent=False, send_at__lte=timezone.now(),
    ).select_related("schedule", "schedule__event")

    reminders_processed = 0
    notifications_created = 0

    with transaction.atomic():
        for reminder in due:
            reminder.sent = True
            reminder.save(update_fields=["sent"])
            reminders_processed += 1

            registrations = reminder.schedule.registrations.filter(
                status=EventRegistrationStatus.CONFIRMED,
            ).select_related("member", "member__user")

<<<<<<< HEAD
            from apps.notifications.models import NotificationCategory
            from apps.notifications.preferences import queue_notification
=======
            from apps.notifications.models import Notification
            from apps.notifications.tasks import deliver_notification
>>>>>>> origin/main

            event = reminder.schedule.event
            for registration in registrations:
                if not registration.member.user_id:
                    continue
<<<<<<< HEAD
                notification = queue_notification(
                    recipient=registration.member.user,
                    recipient_member=registration.member,
                    category=NotificationCategory.EVENT,
                    channel=reminder.channel,
                    title=f"Reminder: {event.title}",
                    body=f"{event.title} starts at {reminder.schedule.occurrence_start:%Y-%m-%d %H:%M}.",
                    idempotency_key=f"event-reminder:{reminder.id}:{registration.member.user_id}:{reminder.channel}",
                )
                if notification:
                    notifications_created += 1
=======
                notification = Notification.objects.create(
                    recipient=registration.member.user,
                    recipient_member=registration.member,
                    channel=reminder.channel,
                    title=f"Reminder: {event.title}",
                    body=f"{event.title} starts at {reminder.schedule.occurrence_start:%Y-%m-%d %H:%M}.",
                )
                deliver_notification.delay(str(notification.id))
                notifications_created += 1
>>>>>>> origin/main

    return {"reminders_processed": reminders_processed, "notifications_created": notifications_created}
