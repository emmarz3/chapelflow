import importlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditLog
from apps.members.models import Member, MembershipStatus


@pytest.mark.django_db
def test_restore_only_stranded_self_registered_members(branch_a):
    registered_at = datetime(2026, 11, 27, 7, 30, tzinfo=timezone.utc)

    def member(email, *, changed=False, membership=MembershipStatus.ACTIVE):
        user = User.objects.create_user(email=email, password="temporary-test-password")
        User.objects.filter(pk=user.pk).update(is_active=False, date_joined=registered_at)
        Member.objects.create(user=user, branch=branch_a, first_name="Test", last_name="Member", membership_status=membership)
        registration = AuditLog.objects.create(user=user, action=AuditAction.MEMBER_SELF_REGISTER, resource_type="member", resource_id="test")
        AuditLog.objects.filter(pk=registration.pk).update(created_at=registered_at)
        if changed:
            AuditLog.objects.create(action=AuditAction.UPDATE, resource_type="accounts.User", resource_id=str(user.pk))
        return user

    eligible = member("eligible-recovery@test.edu")
    deliberately_changed = member("changed-recovery@test.edu", changed=True)
    inactive_member = member("inactive-recovery@test.edu", membership=MembershipStatus.INACTIVE)
    migration = importlib.import_module("apps.accounts.migrations.0018_restore_registration_accounts")
    migration.restore_stranded_registrations(apps, SimpleNamespace(connection=connection))

    eligible.refresh_from_db()
    deliberately_changed.refresh_from_db()
    inactive_member.refresh_from_db()
    assert eligible.is_active
    assert not deliberately_changed.is_active
    assert not inactive_member.is_active
    assert AuditLog.objects.filter(resource_id=str(eligible.pk), metadata__reason="restore_registration_without_email_verification").exists()
