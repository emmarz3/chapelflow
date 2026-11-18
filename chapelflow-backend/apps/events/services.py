from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from .models import Event, EventSchedule, RecurrenceFrequency

_STEP = {
    RecurrenceFrequency.DAILY: lambda dt: dt + timedelta(days=1),
    RecurrenceFrequency.WEEKLY: lambda dt: dt + timedelta(weeks=1),
    RecurrenceFrequency.MONTHLY: lambda dt: dt + relativedelta(months=1),
    RecurrenceFrequency.YEARLY: lambda dt: dt + relativedelta(years=1),
}

MAX_GENERATED_OCCURRENCES = 260  # ~5 years weekly; hard safety cap

DEFAULT_REMINDER_LEAD_TIME = timedelta(hours=24)


def generate_event_schedules(event: Event):
    """
    Materializes EventSchedule rows for an Event. For non-recurring events
    this creates exactly one occurrence. For recurring events it walks
    forward from start_time to recurrence_end_date using the configured
    frequency, capped at MAX_GENERATED_OCCURRENCES to avoid runaway
    generation from a bad end date.
    """
    duration = event.end_time - event.start_time

    if event.frequency == RecurrenceFrequency.NONE or not event.recurrence_end_date:
        schedule, _ = EventSchedule.objects.get_or_create(
            event=event,
            occurrence_start=event.start_time,
            defaults={"occurrence_end": event.end_time},
        )
        schedules = [schedule]
    else:
        step_fn = _STEP[event.frequency]
        schedules = []
        current_start = event.start_time
        count = 0

        while current_start.date() <= event.recurrence_end_date and count < MAX_GENERATED_OCCURRENCES:
            current_end = current_start + duration
            schedule, _ = EventSchedule.objects.get_or_create(
                event=event,
                occurrence_start=current_start,
                defaults={"occurrence_end": current_end},
            )
            schedules.append(schedule)
            current_start = step_fn(current_start)
            count += 1

    for schedule in schedules:
        schedule_default_reminder(schedule)

    return schedules


def schedule_default_reminder(schedule: EventSchedule):
    """
    Spec Phase 7: "Event -> Reminder schedule -> Celery -> Notification.
    Never fake notification delivery." Auto-creates one default reminder
    (DEFAULT_REMINDER_LEAD_TIME before the occurrence) for every generated
    occurrence, in addition to whatever reminders staff schedule manually
    via EventReminder directly. A reminder whose send time has already
    passed (e.g. a short-notice event created less than 24h out) is
    simply not created -- there's nothing useful to remind anyone of.
    """
    from .models import EventReminder

    send_at = schedule.occurrence_start - DEFAULT_REMINDER_LEAD_TIME
    if send_at <= timezone.now():
        return None
    reminder, _ = EventReminder.objects.get_or_create(
        schedule=schedule, send_at=send_at, channel="EMAIL", defaults={"sent": False},
    )
    return reminder


class RegistrationError(ValueError):
    """Raised for any registration failure the view should surface as a clean 4xx, not a 500."""


def register_for_event(schedule: EventSchedule, member) -> tuple:
    """
    Spec Phase 7: capacity, waitlist, cancellation, duplicate prevention,
    registration deadline -- all in one transactional place rather than
    scattered across a serializer's `validate()` (which can't safely hold
    a row lock across a capacity check + insert, and previously let two
    concurrent requests both slip in under a capacity of 1).

    Returns (registration, created: bool). `created` is False when this
    call reactivated an existing CANCELLED registration rather than
    inserting a new row (see EventRegistration.Meta.unique_together).
    """
    from .models import EventRegistration, EventRegistrationStatus

    event = schedule.event
    if not event.requires_registration:
        raise RegistrationError("This event does not require registration.")
    if event.registration_deadline and timezone.now() > event.registration_deadline:
        raise RegistrationError("The registration deadline for this event has passed.")

    with transaction.atomic():
        existing = EventRegistration.objects.select_for_update().filter(schedule=schedule, member=member).first()
        if existing and existing.status != EventRegistrationStatus.CANCELLED:
            raise RegistrationError("You are already registered for this occurrence.")

        # Lock every existing (non-cancelled) registration row for this
        # schedule so two concurrent requests can't both see "1 spot
        # left" and both get CONFIRMED -- this is exactly the race the
        # old serializer-level `.count()` check couldn't prevent.
        confirmed_count = EventRegistration.objects.select_for_update().filter(
            schedule=schedule, status=EventRegistrationStatus.CONFIRMED,
        ).count()

        capacity = event.capacity
        status = (
            EventRegistrationStatus.WAITLISTED
            if capacity is not None and confirmed_count >= capacity
            else EventRegistrationStatus.CONFIRMED
        )

        if existing:
            existing.status = status
            existing.cancelled_at = None
            existing.save(update_fields=["status", "cancelled_at"])
            return existing, False

        registration = EventRegistration.objects.create(schedule=schedule, member=member, status=status)
        return registration, True


def cancel_registration(registration) -> None:
    """
    Cancelling a CONFIRMED spot promotes the longest-waiting WAITLISTED
    registration (if any) to CONFIRMED, atomically, so a cancellation
    never silently leaves an open spot with people still on the waitlist.
    """
    from .models import EventRegistration, EventRegistrationStatus

    with transaction.atomic():
        registration = EventRegistration.objects.select_for_update().get(pk=registration.pk)
        was_confirmed = registration.status == EventRegistrationStatus.CONFIRMED
        registration.status = EventRegistrationStatus.CANCELLED
        registration.cancelled_at = timezone.now()
        registration.save(update_fields=["status", "cancelled_at"])

        if was_confirmed:
            next_in_line = EventRegistration.objects.select_for_update().filter(
                schedule_id=registration.schedule_id, status=EventRegistrationStatus.WAITLISTED,
            ).order_by("registered_at").first()
            if next_in_line:
                next_in_line.status = EventRegistrationStatus.CONFIRMED
                next_in_line.save(update_fields=["status"])
