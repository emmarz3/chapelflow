"""
Phase 11: Member engagement signals.

Automatically generates follow-up tasks when new members join.
"""
from datetime import datetime, time, timedelta
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Member, MemberFollowUp, MemberFollowUpMilestone, MembershipStatus

logger = logging.getLogger(__name__)


def get_default_follow_up_assignee(member):
    """
    Determine who should be assigned new member follow-ups.
    
    Priority:
    1. Member's fellowship leader (if they have a fellowship)
    2. Branch's designated pastoral staff
    3. Branch's chapel admin
    4. None (will need manual assignment)
    """
    from common.constants.roles import Roles
    
    # Try fellowship leader first
    if member.fellowship:
        fellowship_leader = member.fellowship.leader
        if fellowship_leader:
            return fellowship_leader
    
    # Try to find pastoral staff in the branch
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    pastoral_staff = User.objects.filter(
        branch=member.branch,
        role__in=Roles.PASTORAL_ACCESS_ROLES
    ).first()
    
    if pastoral_staff:
        return pastoral_staff
    
    # Fall back to chapel admin
    chapel_admin = User.objects.filter(
        branch=member.branch,
        role__in=Roles.BRANCH_SCOPE_ROLES
    ).first()
    
    return chapel_admin


@receiver(post_save, sender=Member)
def create_new_member_follow_ups(sender, instance, created, **kwargs):
    """
    Phase 11: Auto-generate 7/30/90-day follow-up tasks for new members.
    
    Triggered on Member creation when:
    - Member is newly created (not an update)
    - Member status is ACTIVE
    - Member has a membership_date
    
    Creates 3 MemberFollowUp records with scheduled_for dates at:
    - 7 days after membership_date
    - 30 days after membership_date
    - 90 days after membership_date
    
    Idempotency:
    - unique_together constraint prevents duplicates
    - bulk_create with ignore_conflicts=True handles race conditions
    
    Security:
    - Respects branch boundaries (assigned_to from same branch)
    - Creates records only for ACTIVE members
    """
    # Only for newly created members
    if not created:
        return
    
    # Only for active members
    if instance.membership_status != MembershipStatus.ACTIVE:
        return
    
    # Need a membership date to calculate follow-up dates
    membership_date = instance.membership_date or timezone.now().date()
    
    # Follow-up reminders are ancillary to creating the account. Isolate them
    # in a savepoint so a reminder/configuration failure is logged without
    # rolling back the user's registration transaction.
    try:
        with transaction.atomic():
            assigned_to = get_default_follow_up_assignee(instance)
            follow_ups = []

            for milestone, days_offset in [
                (MemberFollowUpMilestone.DAY_7, 7),
                (MemberFollowUpMilestone.DAY_30, 30),
                (MemberFollowUpMilestone.DAY_90, 90),
            ]:
                scheduled_date = membership_date + timedelta(days=days_offset)
                scheduled_datetime = timezone.make_aware(
                    datetime.combine(scheduled_date, time(9, 0))
                )
                follow_ups.append(
                    MemberFollowUp(
                        member=instance,
                        milestone=milestone,
                        assigned_to=assigned_to,
                        scheduled_for=scheduled_datetime,
                    )
                )

            MemberFollowUp.objects.bulk_create(follow_ups, ignore_conflicts=True)
    except Exception:
        logger.exception("New-member follow-up creation failed for member %s", instance.pk)
