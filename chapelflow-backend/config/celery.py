import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("chapelflow")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Spec Phase 5: "New visitor -> Follow-up task -> Assignment ->
    # Reminder -> Completion... use Celery for scheduled reminders."
    "visitor-follow-up-reminders": {
        "task": "apps.visitors.tasks.send_pending_follow_up_reminders",
        "schedule": 300.0,  # every 5 minutes
    },
    # Spec Phase 7: "Event -> Reminder schedule -> Celery -> Notification."
    "event-reminders": {
        "task": "apps.events.tasks.send_due_event_reminders",
        "schedule": 300.0,  # every 5 minutes
    },
    # Spec Phase 8: "No attendance for configured period -> Pastoral
    # follow-up flag."
    "pastoral-absence-flagging": {
        "task": "apps.pastoral.tasks.flag_members_with_prolonged_absence",
        "schedule": 86400.0,  # once daily
    },
    # Phase 11: Member follow-up reminders (7/30/90-day milestones)
    "member-follow-up-reminders": {
        "task": "apps.members.tasks.send_member_follow_up_reminders",
        "schedule": 3600.0,  # every hour (follow-ups are day-granularity)
    },
    # Phase 11: Recalculate engagement metrics for all active members
    "recalculate-engagement-metrics": {
        "task": "apps.members.tasks.recalculate_engagement_metrics",
        "schedule": 86400.0,  # once daily at configured time
    },
    # Phase 11: Flag members with repeated absence for pastoral follow-up
    "flag-absent-members": {
        "task": "apps.attendance.tasks.flag_absent_members",
        "schedule": 604800.0,  # once weekly (7 days)
    },
    "publish-scheduled-content": {
        "task": "apps.operations.tasks.publish_scheduled_content",
        "schedule": 60.0,
    },
    "dispatch-scheduled-announcements": {
        "task": "apps.communications.tasks.dispatch_scheduled_announcements",
        "schedule": 60.0,
    },
    "birthday-notifications": {
        "task": "apps.notifications.tasks.send_birthday_notifications",
        "schedule": crontab(hour=8, minute=0),
    },
    # Phase 13: Pastoral case follow-up reminders
    "pastoral-follow-up-reminders": {
        "task": "apps.pastoral.tasks.send_pastoral_follow_up_reminders",
        "schedule": 86400.0,  # once daily
    },
    # Phase 13: Prayer request follow-up reminders
    "prayer-follow-up-reminders": {
        "task": "apps.pastoral.tasks.send_prayer_follow_up_reminders",
        "schedule": 86400.0,  # once daily
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
