import pytest
from django.utils import timezone

from apps.members.models import Member
from apps.notifications.models import BirthdayAnnouncement, Notification, NotificationChannel
from apps.notifications.tasks import send_birthday_notifications


pytestmark = pytest.mark.django_db


def test_birthday_job_notifies_each_active_user_once_per_branch(make_user, branch_a):
    celebrant_user = make_user(email="birthday@test.edu", branch=branch_a)
    Member.objects.create(
        user=celebrant_user,
        branch=branch_a,
        first_name="Birthday",
        last_name="Student",
        date_of_birth=timezone.localdate().replace(year=timezone.localdate().year - 20),
    )
    colleague = make_user(email="colleague@test.edu", branch=branch_a)

    first = send_birthday_notifications()
    second = send_birthday_notifications()

    assert first == {"celebrations_created": 1, "notifications_created": 2}
    assert second == {"celebrations_created": 0, "notifications_created": 0}
    assert BirthdayAnnouncement.objects.count() == 1
    assert Notification.objects.filter(channel=NotificationChannel.IN_APP).count() == 2
    assert Notification.objects.filter(recipient=colleague, title__startswith="Happy birthday").exists()
