"""
Phase 9: volunteer assignment lifecycle + conflict detection.

Kept as plain functions (not viewset methods) so both the API layer and
tests/other services (e.g. a future bulk-scheduling tool) can call the
same, single-source-of-truth checks. Every conflict is raised as a DRF
ValidationError so viewsets can let it propagate straight into a 400
response without translation.

Security:
- All FK relationships validated by serializers before reaching services
- Conflict detection prevents double-booking
- Availability windows respected
- Group scope validated (volunteer and group in same branch)
- Status transitions controlled (cannot skip states)
- Historical data protected (completed assignments immutable)
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import AssignmentStatus, VolunteerAssignment


def _overlaps(a_start, a_end, b_start, b_end):
    """Check if two time ranges overlap."""
    return a_start < b_end and b_start < a_end


def check_duplicate_assignment(volunteer, event_schedule, role, exclude_id=None):
    """
    Same volunteer, same occurrence, same role, not yet declined/cancelled -> duplicate.
    
    Prevents creating redundant assignments that would confuse scheduling.
    """
    if event_schedule is None:
        return
    qs = VolunteerAssignment.objects.filter(
        volunteer=volunteer, event_schedule=event_schedule, role=role,
    ).exclude(status__in=[AssignmentStatus.DECLINED, AssignmentStatus.CANCELLED])
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        raise ValidationError(
            {"detail": "This volunteer already has an assignment for this role at this occurrence."}
        )


def check_overlap_conflict(volunteer, event_schedule, exclude_id=None):
    """
    A volunteer cannot be double-booked: any other active (PENDING/
    CONFIRMED) assignment whose occurrence time-range overlaps this one is
    a conflict, regardless of role or Group.
    
    Security: Prevents volunteers from being assigned to overlapping events.
    """
    if event_schedule is None:
        return
    active = VolunteerAssignment.objects.filter(
        volunteer=volunteer, status__in=[AssignmentStatus.PENDING, AssignmentStatus.CONFIRMED],
    ).exclude(event_schedule__isnull=True).select_related("event_schedule")
    if exclude_id:
        active = active.exclude(id=exclude_id)

    for other in active:
        if _overlaps(
            event_schedule.occurrence_start, event_schedule.occurrence_end,
            other.event_schedule.occurrence_start, other.event_schedule.occurrence_end,
        ):
            raise ValidationError(
                {"detail": f"This volunteer already has an overlapping assignment ({other.role}) at this time."}
            )


def check_availability_conflict(volunteer, event_schedule):
    """
    Cross-check the occurrence's weekday/time-of-day against any
    VolunteerAvailability row the volunteer marked unavailable
    (is_available=False) for that window.
    
    Respects volunteer preferences for when they are NOT available to serve.
    """
    if event_schedule is None:
        return
    local_start = timezone.localtime(event_schedule.occurrence_start)
    weekday = local_start.weekday()
    start_t = local_start.time()
    end_t = timezone.localtime(event_schedule.occurrence_end).time()

    blocked = volunteer.availability.filter(weekday=weekday, is_available=False)
    for window in blocked:
        if _overlaps(start_t, end_t, window.start_time, window.end_time):
            raise ValidationError(
                {"detail": "This volunteer has marked themselves unavailable during this time window."}
            )


def check_group_scope(group, volunteer):
    """
    A volunteer can only be assigned under a Group in their own branch.
    
    Security: Prevents cross-branch assignment attacks.
    """
    if group is not None and group.branch_id != volunteer.member.branch_id:
        raise ValidationError({"group": "This Group does not belong to the volunteer's branch."})


def run_conflict_checks(volunteer, event_schedule, role, group, exclude_id=None):
    """
    Run all business rule validations before creating/confirming assignment.
    
    Called at creation AND confirmation to catch changes that happened between.
    """
    check_group_scope(group, volunteer)
    check_duplicate_assignment(volunteer, event_schedule, role, exclude_id=exclude_id)
    check_overlap_conflict(volunteer, event_schedule, exclude_id=exclude_id)
    check_availability_conflict(volunteer, event_schedule)


@transaction.atomic
def create_assignment(volunteer, event_schedule, role, group=None, notes=""):
    """
    Create a new volunteer assignment with conflict detection.
    
    Security:
    - FK scope validated by serializers before calling this
    - Conflict checks prevent invalid assignments
    - Initial status is PENDING (requires confirmation)
    - confirmed field set to False for backward compatibility
    
    Returns: VolunteerAssignment instance
    """
    run_conflict_checks(volunteer, event_schedule, role, group)
    return VolunteerAssignment.objects.create(
        volunteer=volunteer, 
        event_schedule=event_schedule, 
        role=role, 
        group=group, 
        notes=notes,
        status=AssignmentStatus.PENDING,
        confirmed=False,  # Explicit backward compatibility
    )


@transaction.atomic
def confirm_assignment(assignment):
    """
    Confirm a PENDING assignment (PENDING -> CONFIRMED).
    
    Security:
    - Only PENDING assignments can be confirmed
    - Re-validates conflicts at confirmation time (assignments may have changed)
    - Sets responded_at timestamp
    - Syncs confirmed=True for backward compatibility
    
    Returns: Updated VolunteerAssignment instance
    """
    if assignment.status not in (AssignmentStatus.PENDING,):
        raise ValidationError({"detail": f"Cannot confirm an assignment in status {assignment.status}."})
    
    # Re-run overlap/availability checks at confirmation time too -- the
    # volunteer's other assignments or availability may have changed since
    # this one was first created as PENDING.
    check_overlap_conflict(assignment.volunteer, assignment.event_schedule, exclude_id=assignment.id)
    check_availability_conflict(assignment.volunteer, assignment.event_schedule)
    
    assignment.status = AssignmentStatus.CONFIRMED
    assignment.confirmed = True  # Sync for backward compatibility
    assignment.responded_at = timezone.now()
    assignment.save(update_fields=["status", "confirmed", "responded_at"])
    return assignment


@transaction.atomic
def decline_assignment(assignment, reason=""):
    """
    Decline an assignment with optional reason (PENDING/CONFIRMED -> DECLINED).
    
    Security:
    - Cannot decline COMPLETED or CANCELLED assignments (historical protection)
    - Sets responded_at timestamp
    - Syncs confirmed=False for backward compatibility
    - Appends reason to notes if provided
    
    Returns: Updated VolunteerAssignment instance
    """
    if assignment.status in (AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED):
        raise ValidationError({"detail": f"Cannot decline an assignment in status {assignment.status}."})
    
    assignment.status = AssignmentStatus.DECLINED
    assignment.confirmed = False  # Sync for backward compatibility
    assignment.responded_at = timezone.now()
    
    if reason:
        assignment.notes = (assignment.notes + f" | Declined: {reason}").strip(" |")
    
    assignment.save(update_fields=["status", "confirmed", "responded_at", "notes"])
    return assignment


@transaction.atomic
def complete_assignment(assignment, hours_logged):
    """
    Complete a CONFIRMED assignment with service hours (CONFIRMED -> COMPLETED).
    
    Security:
    - Only CONFIRMED assignments can be completed (must confirm first)
    - Validates hours_logged >= 0
    - Sets completed_at timestamp
    - Completed assignments are historical (immutable)
    - confirmed remains True (was confirmed, now completed)
    
    Returns: Updated VolunteerAssignment instance
    """
    if assignment.status != AssignmentStatus.CONFIRMED:
        raise ValidationError({"detail": "Only a CONFIRMED assignment can be marked complete."})
    
    if hours_logged is None or hours_logged < 0:
        raise ValidationError({"hours_logged": "A non-negative number of hours is required to log service history."})
    
    assignment.status = AssignmentStatus.COMPLETED
    assignment.hours_logged = hours_logged
    assignment.completed_at = timezone.now()
    # confirmed stays True (it WAS confirmed, and now it's completed)
    
    assignment.save(update_fields=["status", "hours_logged", "completed_at"])
    return assignment


@transaction.atomic
def cancel_assignment(assignment, reason=""):
    """
    Cancel an assignment (any status except COMPLETED -> CANCELLED).
    
    Security:
    - Cannot cancel COMPLETED assignments (historical protection)
    - Syncs confirmed=False for backward compatibility
    - Appends reason to notes if provided
    
    Returns: Updated VolunteerAssignment instance
    """
    if assignment.status == AssignmentStatus.COMPLETED:
        raise ValidationError({"detail": "Cannot cancel a completed assignment. Historical data is protected."})
    
    assignment.status = AssignmentStatus.CANCELLED
    assignment.confirmed = False  # Sync for backward compatibility
    
    if reason:
        assignment.notes = (assignment.notes + f" | Cancelled: {reason}").strip(" |")
    
    assignment.save(update_fields=["status", "confirmed", "notes"])
    return assignment
