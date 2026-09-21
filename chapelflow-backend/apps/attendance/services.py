import logging
import hashlib
import time
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.members.models import Member, MemberQRCode, is_student_community_member
from common.permissions.scoping import user_can_access_branch
from .models import (
    AttendanceCheckpoint, AttendanceMethod, AttendanceRecord, AttendanceScanAttempt,
    AttendanceSession, AttendanceSessionState, AttendanceStatus,
)

logger = logging.getLogger("chapelflow.audit")

# Grace period for late arrival (configurable via settings in production)
LATE_ARRIVAL_GRACE_MINUTES = 15


class AttendanceError(Exception):
    """Raised for any attendance validation failure; view maps to a 4xx response."""


QR_ROTATION_SECONDS = 45
QR_TOKEN_SALT = "chapelflow.attendance.usher.v1"


def _attendance_window_is_open(session: AttendanceSession, now=None) -> bool:
    now = now or timezone.now()
    return (
        session.is_open
        and session.state == AttendanceSessionState.OPEN
        and (not session.window_opens_at or now >= session.window_opens_at)
        and (not session.window_closes_at or now <= session.window_closes_at)
    )


def issue_checkpoint_token(checkpoint: AttendanceCheckpoint) -> dict:
    """Issue a signed, opaque token for this usher's current 45-second slice."""
    now = timezone.now()
    session = checkpoint.session
    if not _attendance_window_is_open(session, now):
        raise AttendanceError("Attendance is not currently open.")
    if not checkpoint.usher.is_active:
        raise AttendanceError("This usher account is inactive.")

    now_epoch = int(now.timestamp())
    expires_epoch = ((now_epoch // QR_ROTATION_SECONDS) + 1) * QR_ROTATION_SECONDS
    payload = {"c": str(checkpoint.id), "s": str(session.id), "e": expires_epoch}
    return {
        "token": signing.dumps(payload, salt=QR_TOKEN_SALT, compress=True),
        "expires_at": datetime.fromtimestamp(expires_epoch, tz=dt_timezone.utc),
        "rotation_seconds": QR_ROTATION_SECONDS,
    }


def _safe_token_reference(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:64]


def _record_scan_attempt(*, token: str, result: str, session=None, checkpoint=None, student=None) -> None:
    AttendanceScanAttempt.objects.create(
        session=session, checkpoint=checkpoint, student=student,
        token_reference=_safe_token_reference(token), result=result,
    )


def student_scan_usher_token(*, token: str, user):
    """Record the logged-in student's scan of a live usher QR, never a personal QR."""
    member = Member.objects.select_related("branch").filter(user=user).first()
    if user.get_role_code() != "MEMBER" or not is_student_community_member(member):
        _record_scan_attempt(token=token, result="unauthorized_role")
        raise AttendanceError("Only authenticated student accounts can record attendance.")
    if not user.is_active or member.membership_status != "ACTIVE":
        _record_scan_attempt(token=token, result="student_inactive", student=member)
        raise AttendanceError("Your student account is inactive.")

    try:
        payload = signing.loads(token, salt=QR_TOKEN_SALT, max_age=QR_ROTATION_SECONDS + 5)
        expires_epoch = int(payload["e"])
        if int(time.time()) >= expires_epoch:
            raise signing.BadSignature("expired")
        checkpoint_id, session_id = payload["c"], payload["s"]
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        _record_scan_attempt(token=token, result="invalid_or_expired", student=member)
        raise AttendanceError("This attendance QR code is invalid or has expired.")

    checkpoint = AttendanceCheckpoint.objects.select_related("session", "usher").filter(
        id=checkpoint_id, session_id=session_id,
    ).first()
    if not checkpoint:
        _record_scan_attempt(token=token, result="invalid_checkpoint", student=member)
        raise AttendanceError("This attendance QR code is invalid.")
    session = checkpoint.session
    if checkpoint.usher.get_role_code() != "ATTENDANCE_USHER" or not checkpoint.usher.is_active:
        _record_scan_attempt(token=token, result="usher_inactive", session=session, checkpoint=checkpoint, student=member)
        raise AttendanceError("This attendance checkpoint is unavailable.")
    if member.branch_id != session.branch_id:
        _record_scan_attempt(token=token, result="wrong_branch", session=session, checkpoint=checkpoint, student=member)
        raise AttendanceError("This attendance QR code is not for your chapel service.")
    if not _attendance_window_is_open(session):
        _record_scan_attempt(token=token, result="session_unavailable", session=session, checkpoint=checkpoint, student=member)
        raise AttendanceError("Attendance is not currently open.")

    record, created = _create_record(
        session=session, member=member, method=AttendanceMethod.QR_CODE,
        checked_in_by=checkpoint.usher, checkpoint=checkpoint, checked_in_at=timezone.now(),
    )
    _record_scan_attempt(
        token=token, result="recorded" if created else "duplicate", session=session,
        checkpoint=checkpoint, student=member,
    )
    return record, created


def get_or_open_session(branch, event_schedule=None, label=""):
    if event_schedule is not None:
        session, _ = AttendanceSession.objects.get_or_create(
            branch=branch, event_schedule=event_schedule, is_open=True,
            defaults={"label": label},
        )
        return session
    return AttendanceSession.objects.create(branch=branch, label=label)


def resolve_member_from_qr_token(token: str) -> Member:
    """
    QR codes encode ONLY a random token, never PII. This resolves that
    token to a member record server-side.
    """
    qr = (
        MemberQRCode.objects.select_related("member", "member__branch")
        .filter(token=token, is_active=True)
        .first()
    )
    if not qr:
        raise AttendanceError("Invalid or inactive QR code.")
    return qr.member


def qr_check_in(*, token: str, session: AttendanceSession, device=None, checked_in_by=None):
    member = resolve_member_from_qr_token(token)

    if member.branch_id != session.branch_id:
        raise AttendanceError("This QR code belongs to a member outside this branch/session.")

    return _create_record(
        session=session, member=member, method=AttendanceMethod.QR_CODE,
        device=device, checked_in_by=checked_in_by, checked_in_at=timezone.now(),
    )


def manual_check_in(*, member: Member, session: AttendanceSession, checked_in_by):
    return _create_record(
        session=session, member=member, method=AttendanceMethod.MANUAL,
        checked_in_by=checked_in_by, checked_in_at=timezone.now(),
    )


def self_check_in(*, member: Member, session: AttendanceSession):
    """
    Phase 7 security enhancement: Self-service check-in where member is
    derived from authenticated user (not from client-supplied ID).
    """
    return _create_record(
        session=session, member=member, method=AttendanceMethod.SELF_CHECK_IN,
        checked_in_by=None,  # Self-service, no staff user
        checked_in_at=timezone.now(),
    )


def kiosk_check_in(*, token: str, session: AttendanceSession, device, device_secret: str):
    """
    CRITICAL Phase 8 fix: previously this accepted an *optional*,
    completely unauthenticated `device` (just an ID lookup -- no secret,
    no is_active check), despite this endpoint's own docstring calling
    itself "device-authenticated". Confirmed as a live gap: a caller
    could omit device_id entirely, or pass ANY device id (even a
    deactivated/revoked one) and it would silently succeed. Now the
    device is mandatory, must be active, must belong to the session's
    branch, and must present its own rotating secret (see
    CheckInDevice.verify_secret) -- independent of whatever staff account
    happens to be logged into the kiosk browser.
    """
    if device is None:
        raise AttendanceError("A registered device is required for kiosk check-in.")
    if not device.is_active:
        raise AttendanceError("This device has been deactivated. Contact an administrator.")
    if device.branch_id != session.branch_id:
        raise AttendanceError("This device is not registered for this branch/session.")
    if not device.verify_secret(device_secret):
        raise AttendanceError("Invalid device credentials.")

    device.last_seen_at = timezone.now()
    device.save(update_fields=["last_seen_at"])

    member = resolve_member_from_qr_token(token)
    if member.branch_id != session.branch_id:
        raise AttendanceError("This QR code belongs to a member outside this branch/session.")
    return _create_record(
        session=session, member=member, method=AttendanceMethod.KIOSK,
        device=device, checked_in_at=timezone.now(),
    )


def _create_record(*, session, member, method, checked_in_at, device=None, checked_in_by=None, checkpoint=None, client_record_id=None, synced_at=None):
    """
    Create attendance record with:
    - Duplicate prevention (transaction + unique constraint)
    - Late arrival detection (server-side, based on event start time)
    - EventRegistration.attended synchronization (Phase 6 integration)
    """
    # Determine status (PRESENT or LATE) based on event start time
    status = AttendanceStatus.PRESENT
    if session.event_schedule:
        grace_period = timedelta(minutes=LATE_ARRIVAL_GRACE_MINUTES)
        if checked_in_at > session.event_schedule.occurrence_start + grace_period:
            status = AttendanceStatus.LATE
    
    try:
        with transaction.atomic():
            record, created = AttendanceRecord.objects.get_or_create(
                session=session,
                member=member,
                defaults={
                    "method": method,
                    "status": status,
                    "device": device,
                    "checked_in_by": checked_in_by,
                    "checkpoint": checkpoint,
                    "checked_in_at": checked_in_at,
                    "client_record_id": client_record_id,
                    "synced_at": synced_at,
                },
            )
            
            # CRITICAL Phase 7 enhancement: Sync EventRegistration.attended
            # This bridges Phase 6 (events/registration) with Phase 7 (attendance)
            if created and session.event_schedule and member:
                _sync_event_registration_attended(session.event_schedule, member)
    except IntegrityError:
        # Race condition: two simultaneous check-ins for the same member/session.
        record = AttendanceRecord.objects.get(session=session, member=member)
        created = False

    if not created:
        logger.info(
            "duplicate_attendance_blocked member_id=%s session_id=%s", member.id, session.id
        )
    return record, created


def _sync_event_registration_attended(event_schedule, member):
    """
    Phase 6/7 integration: Mark EventRegistration.attended = True when
    member checks in to an EventSchedule's attendance session.
    
    This enables:
    - Event attendance reporting
    - No-show analysis (registered but not attended)
    - Waitlist vs attendance comparison
    """
    from apps.events.models import EventRegistration, EventRegistrationStatus
    
    EventRegistration.objects.filter(
        schedule=event_schedule,
        member=member,
        status=EventRegistrationStatus.CONFIRMED,
    ).update(attended=True)


def attendance_analytics(queryset, *, days=90):
    """
    Spec Phase 8: "attendance trends, attendance rate, no-show rate,
    member history, aggregates, heatmap-ready data". `queryset` is the
    caller's own already-scoped AttendanceRecord queryset (branch/org/
    leader), so a Fellowship Leader only ever sees stats for their own
    people, never the whole branch.

    "No-show rate" is computed against events.EventRegistration (a
    member who registered for an occurrence but has no matching
    AttendanceRecord for that occurrence's session), not against every
    session generally -- attendance without a registration requirement
    doesn't have a meaningful "no-show" concept.
    """
    from collections import defaultdict
    from django.utils import timezone
    from apps.events.models import EventRegistration, EventRegistrationStatus

    since = timezone.now() - timezone.timedelta(days=days)
    recent = queryset.filter(checked_in_at__gte=since)

    # Trend: count per calendar day (heatmap-ready: day -> count).
    trend = defaultdict(int)
    for checked_in_at in recent.values_list("checked_in_at", flat=True):
        trend[checked_in_at.date().isoformat()] += 1

    member_ids_present = set(recent.exclude(member__isnull=True).values_list("member_id", flat=True))

    # No-show rate: CONFIRMED registrations for schedules whose sessions
    # fall inside the same window, cross-referenced against actual
    # check-ins for that same session.
    registrations = EventRegistration.objects.filter(
        status=EventRegistrationStatus.CONFIRMED,
        schedule__occurrence_start__gte=since,
        schedule__attendance_sessions__isnull=False,
    ).select_related("schedule").distinct()

    total_registered = 0
    no_shows = 0
    checked_in_member_session_pairs = set(
        recent.exclude(member__isnull=True).values_list("member_id", "session_id")
    )
    for reg in registrations:
        for session in reg.schedule.attendance_sessions.all():
            total_registered += 1
            if (reg.member_id, session.id) not in checked_in_member_session_pairs:
                no_shows += 1
            break  # one attendance session per schedule in normal use; avoid double-counting an edge case

    return {
        "window_days": days,
        "total_check_ins": recent.count(),
        "unique_members_present": len(member_ids_present),
        "daily_trend": dict(sorted(trend.items())),
        "no_show_rate": round(no_shows / total_registered * 100, 1) if total_registered else 0.0,
        "registrations_considered": total_registered,
    }


def member_attendance_history(queryset, member_id):
    """Spec Phase 8: 'member history' -- every check-in for one member, within the caller's own scope."""
    records = queryset.filter(member_id=member_id).select_related("session", "session__event_schedule").order_by("-checked_in_at")
    return [
        {
            "id": str(r.id), "session_id": str(r.session_id), "method": r.method,
            "checked_in_at": r.checked_in_at,
        }
        for r in records
    ]


def sync_offline_records(*, records: list[dict], branch, submitted_by):
    """
    Processes a batch of offline-queued attendance records.

    Each record must include a client-generated `client_record_id` used as
    an idempotency key: re-submitting the same batch (e.g. after a flaky
    connection) never creates duplicates, because client_record_id is
    unique at the DB level and re-submission just returns the existing row.

    Returns a per-record success/failure report so the frontend can retry
    only the records that actually failed.
    """
    results = []

    for idx, item in enumerate(records):
        client_id = item.get("client_record_id")
        if not client_id:
            results.append({"index": idx, "status": "failed", "error": "client_record_id is required."})
            continue

        existing = AttendanceRecord.objects.filter(client_record_id=client_id).first()
        if existing:
            results.append({"index": idx, "status": "already_synced", "record_id": str(existing.id)})
            continue

        try:
            member = Member.objects.get(id=item["member_id"], branch=branch)
        except (Member.DoesNotExist, KeyError):
            results.append({"index": idx, "status": "failed", "error": "Member not found in this branch."})
            continue

        session_id = item.get("session_id")
        try:
            session = AttendanceSession.objects.get(id=session_id, branch=branch)
        except (AttendanceSession.DoesNotExist, KeyError):
            results.append({"index": idx, "status": "failed", "error": "Attendance session not found."})
            continue

        checked_in_at = item.get("checked_in_at")
        if not checked_in_at:
            results.append({"index": idx, "status": "failed", "error": "checked_in_at is required."})
            continue

        record, created = _create_record(
            session=session,
            member=member,
            method=item.get("method", AttendanceMethod.SELF_CHECK_IN),
            checked_in_at=checked_in_at,
            checked_in_by=submitted_by,
            client_record_id=client_id,
            synced_at=timezone.now(),
        )

        if created:
            results.append({"index": idx, "status": "synced", "record_id": str(record.id)})
        else:
            results.append({"index": idx, "status": "duplicate_member_session", "record_id": str(record.id)})

    return results


def generate_absences_for_session(session: AttendanceSession):
    """
    Phase 7 enhancement: Generate absence records for registered members
    who didn't check in when session closes.
    
    Only for event-linked sessions (session.event_schedule is not None).
    Creates AttendanceRecord with status=ABSENT for no-shows.
    """
    if not session.event_schedule:
        return {"absences_created": 0}
    
    from apps.events.models import EventRegistration, EventRegistrationStatus
    
    # Find CONFIRMED registrations for this event occurrence
    registrations = EventRegistration.objects.filter(
        schedule=session.event_schedule,
        status=EventRegistrationStatus.CONFIRMED,
    ).select_related("member")
    
    # Find who already checked in
    checked_in_member_ids = set(
        AttendanceRecord.objects.filter(
            session=session,
            member__isnull=False,
        ).values_list("member_id", flat=True)
    )
    
    # Create absence records for no-shows
    absences_created = 0
    for reg in registrations:
        if reg.member_id not in checked_in_member_ids:
            _, created = AttendanceRecord.objects.get_or_create(
                session=session,
                member=reg.member,
                defaults={
                    "method": AttendanceMethod.MANUAL,
                    "status": AttendanceStatus.ABSENT,
                    "checked_in_at": session.closed_at or timezone.now(),
                }
            )
            if created:
                absences_created += 1
    
    return {"absences_created": absences_created}



def detect_repeated_absence(member, threshold_weeks=3):
    """
    Phase 11: Check if member hasn't attended in threshold_weeks.
    
    Args:
        member: Member instance
        threshold_weeks: Number of weeks to look back (default: 3)
    
    Returns:
        bool: True if member has been absent for threshold_weeks, False otherwise
    
    Used by:
    - Absence flagging task
    - Pastor dashboard (inactive member alerts)
    - Fellowship leader reports
    """
    cutoff = timezone.now() - timedelta(weeks=threshold_weeks)
    
    # Check if member has ANY attendance in the threshold period
    recent_attendance = AttendanceRecord.objects.filter(
        member=member,
        checked_in_at__gte=cutoff
    ).exists()
    
    return not recent_attendance


def create_attendance_follow_up(member):
    """
    Phase 11: Create pastoral case for member with repeated absence.
    
    Args:
        member: Member instance who has been absent
    
    Returns:
        PastoralCase instance or None if case already exists
    
    Creates a pastoral case with:
    - Category: "Attendance Concern"
    - Assigned to: Member's fellowship leader or pastoral staff
    - Summary: Automated absence detection message
    
    Idempotency:
    - Checks if open case already exists for this member + category
    - Only creates if no existing open case
    """
    from apps.pastoral.models import PastoralCase, PastoralCaseStatus
    
    # Check if case already exists
    existing_case = PastoralCase.objects.filter(
        member=member,
        status__in=[PastoralCaseStatus.OPEN, PastoralCaseStatus.IN_PROGRESS],
        category__icontains="Attendance"
    ).first()
    
    if existing_case:
        logger.info(
            f"Attendance follow-up for member {member.id} skipped - "
            f"existing case {existing_case.id} already open"
        )
        return None
    
    # Find appropriate assignee (fellowship leader or pastoral staff)
    assigned_to = None
    if member.fellowship and member.fellowship.leader:
        assigned_to = member.fellowship.leader
    else:
        # Fall back to pastoral staff
        from django.contrib.auth import get_user_model
        from common.constants.roles import Roles
        User = get_user_model()
        
        pastoral_staff = User.objects.filter(
            branch=member.branch,
            role__in=Roles.PASTORAL_ACCESS_ROLES
        ).first()
        
        assigned_to = pastoral_staff
    
    # Create pastoral case
    case = PastoralCase.objects.create(
        branch=member.branch,
        member=member,
        assigned_to=assigned_to,
        category="Attendance Concern",
        summary=(
            f"Automated detection: {member.full_name} has been absent for multiple weeks. "
            f"Requires follow-up to check on their wellbeing and engagement."
        ),
        status=PastoralCaseStatus.OPEN
    )
    
    logger.info(
        f"Created attendance follow-up case {case.id} for member {member.id} "
        f"assigned to {assigned_to.id if assigned_to else 'unassigned'}"
    )
    
    return case
