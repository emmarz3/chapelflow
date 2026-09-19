import csv
import io

from django.db import transaction

from apps.organizations.models import Branch
from .models import Member, MembershipHistory, MembershipStatus


REQUIRED_COLUMNS = {"first_name", "last_name", "branch_id"}


def parse_and_import_members(csv_file, requesting_user):
    """
    Synchronous import for small/medium files (called directly by the view).
    Large files should instead be dispatched to the Celery task
    (apps.members.tasks.bulk_import_members_task) which calls this same
    function from a background worker.
    """
    decoded = csv_file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))

    if not REQUIRED_COLUMNS.issubset(set(reader.fieldnames or [])):
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    created, updated, failed = 0, 0, 0
    row_results = []

    from common.permissions.scoping import user_can_access_branch

    for idx, row in enumerate(reader, start=2):  # header is row 1
        row_errors = {}

        branch_id = (row.get("branch_id") or "").strip()
        branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
        if not branch:
            row_errors["branch_id"] = ["Branch not found."]
        elif not user_can_access_branch(requesting_user, branch.id):
            row_errors["branch_id"] = ["You are not authorized to import members into this branch."]

        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()
        if not first_name:
            row_errors["first_name"] = ["Required."]
        if not last_name:
            row_errors["last_name"] = ["Required."]

        email = (row.get("email") or "").strip()
        phone = (row.get("phone") or "").strip()

        if row_errors:
            failed += 1
            row_results.append({"row": idx, "status": "failed", "errors": row_errors})
            continue

        try:
            with transaction.atomic():
                existing = None
                if email:
                    existing = Member.objects.filter(branch=branch, email__iexact=email).first()
                if not existing and phone:
                    existing = Member.objects.filter(branch=branch, phone_number=phone).first()

                if existing:
                    existing.first_name = first_name
                    existing.last_name = last_name
                    existing.email = email or existing.email
                    existing.phone_number = phone or existing.phone_number
                    existing.save()
                    updated += 1
                    row_results.append({"row": idx, "status": "updated"})
                else:
                    Member.objects.create(
                        branch=branch,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        phone_number=phone,
                        membership_status=row.get("membership_status") or MembershipStatus.ACTIVE,
                    )
                    created += 1
                    row_results.append({"row": idx, "status": "created"})
        except Exception as exc:  # noqa: BLE001 - surface as a row-level failure, not a 500
            failed += 1
            row_results.append({"row": idx, "status": "failed", "errors": {"non_field_errors": [str(exc)]}})

    return {
        "total": created + updated + failed,
        "created": created,
        "updated": updated,
        "failed": failed,
        "row_results": row_results,
    }


def find_duplicate_members(queryset):
    """
    Simple, explainable duplicate detection (spec section 8): group by
    normalized (first_name, last_name, email-or-phone) within the given
    (already branch-scoped) queryset. Deliberately conservative — false
    negatives are safer than false positives when the result feeds a
    human-reviewed merge action.
    """
    from collections import defaultdict

    buckets = defaultdict(list)
    for member in queryset.only("id", "first_name", "last_name", "email", "phone_number"):
        key = (
            member.first_name.strip().lower(),
            member.last_name.strip().lower(),
            (member.email or "").strip().lower() or (member.phone_number or "").strip(),
        )
        if key[2]:  # require at least one contact point to match on, not just name
            buckets[key].append(member)

    return [
        {
            "candidates": [{"id": str(m.id), "full_name": m.full_name} for m in members],
            "matched_on": {"first_name": key[0], "last_name": key[1], "contact": key[2]},
        }
        for key, members in buckets.items()
        if len(members) > 1
    ]


def merge_members(keep, merged, changed_by):
    """
    Phase 4: Reassign ALL related records from `merged` onto `keep`, then
    deactivate (never hard-delete) `merged` so history/audit trail is preserved.
    
    This atomic transaction reassigns:
    - Group memberships (existing)
    - Tags (existing)
    - Volunteer profile (existing)
    - Event registrations (Phase 4)
    - Attendance records (Phase 4)
    - Visitor attendance (Phase 4)
    - Pastoral cases (Phase 4)
    - Prayer requests (Phase 4)
    - Giving records & pledges (Phase 4)
    - Notifications (Phase 4)
    - Follow-ups (Phase 11)
    - Engagement metrics (Phase 11)
    
    Note: Audit logs, MembershipHistory, and other immutable historical records
    are NOT reassigned — they maintain their original references to preserve
    the full audit trail showing what actions were taken on the merged member
    before deactivation.
    """
    from django.core.exceptions import ObjectDoesNotExist

    def related(instance, accessor):
        try:
            return getattr(instance, accessor)
        except ObjectDoesNotExist:
            return None

    reassigned = {}

    def add_count(name, count=1):
        if count:
            reassigned[name] = reassigned.get(name, 0) + count

    with transaction.atomic():
        # Lock both identities so concurrent merge requests cannot move the
        # same related rows twice or create conflicting canonical records.
        locked = {
            member.id: member
            for member in Member.objects.select_for_update().select_related("user").filter(
                id__in=[keep.id, merged.id]
            )
        }
        keep = locked.get(keep.id)
        merged = locked.get(merged.id)
        if keep is None or merged is None:
            raise ValueError("One or both members no longer exist.")
        if keep.id == merged.id:
            raise ValueError("A member cannot be merged into itself.")
        if keep.branch_id != merged.branch_id:
            raise ValueError("Members must belong to the same branch before they can be merged.")

        previous_status = merged.membership_status

        # Preserve the usable login identity. If both records have accounts,
        # the non-canonical account is disabled but retained for audit history.
        if merged.user_id and not keep.user_id:
            keep.user = merged.user
            keep.save(update_fields=["user", "updated_at"])
            merged.user = None
            add_count("user_account")
        elif merged.user_id and keep.user_id and merged.user_id != keep.user_id:
            merged.user.is_active = False
            merged.user.save(update_fields=["is_active"])
            add_count("user_account_deactivated")

        # Relationships without a per-member uniqueness constraint can move
        # in one SQL statement. Field names are explicit: not every model uses
        # `member` (notifications use recipient_member, scans use student).
        simple_relations = [
            ("invited_visitors_v2", "invited_by"),
            ("headed_households", "head"),
            ("led_groups", "leader"),
            ("group_tasks", "assignee"),
            ("attendance_scan_attempts", "student"),
            ("invited_visitors", "invited_by"),
            ("giving_records", "member"),
            ("pledges", "member"),
            ("payments", "member"),
            ("notifications", "recipient_member"),
            ("prayer_requests", "member"),
            ("pastoral_cases", "member"),
        ]
        for accessor, field_name in simple_relations:
            count = getattr(merged, accessor).all().update(**{field_name: keep})
            add_count(accessor, count)

        # Tags are unique by (member, label). Duplicate labels collapse.
        for item in list(merged.tags.select_for_update()):
            if keep.tags.filter(label=item.label).exists():
                item.delete()
                add_count("tags_consolidated")
            else:
                item.member = keep
                item.save(update_fields=["member"])
                add_count("tags")

        # Group membership keeps the strongest role, earliest join date and
        # active state when the same person appears twice in one group.
        role_rank = {"MEMBER": 0, "ASSISTANT_LEADER": 1, "LEADER": 2}
        for item in list(merged.group_memberships.select_for_update()):
            existing = keep.group_memberships.filter(group=item.group).first()
            if existing is None:
                item.member = keep
                item.save(update_fields=["member"])
                add_count("group_memberships")
                continue
            if role_rank.get(item.role, 0) > role_rank.get(existing.role, 0):
                existing.role = item.role
            existing.is_active = existing.is_active or item.is_active
            existing.joined_at = min(existing.joined_at, item.joined_at)
            existing.save(update_fields=["role", "is_active", "joined_at"])
            item.delete()
            add_count("group_memberships_consolidated")

        # Reviewable join requests are unique by (group, member). Prefer an
        # approved result, then a pending one, while retaining resolution data.
        request_rank = {"REJECTED": 0, "PENDING": 1, "APPROVED": 2}
        for item in list(merged.group_join_requests.select_for_update()):
            existing = keep.group_join_requests.filter(group=item.group).first()
            if existing is None:
                item.member = keep
                item.save(update_fields=["member"])
                add_count("group_join_requests")
                continue
            if request_rank.get(item.status, 0) > request_rank.get(existing.status, 0):
                existing.status = item.status
                existing.resolved_at = item.resolved_at
                existing.resolved_by = item.resolved_by
            if not existing.message and item.message:
                existing.message = item.message
            existing.save(update_fields=["status", "resolved_at", "resolved_by", "message"])
            item.delete()
            add_count("group_join_requests_consolidated")

        for item in list(merged.group_meeting_attendance.select_for_update()):
            existing = keep.group_meeting_attendance.filter(meeting=item.meeting).first()
            if existing is None:
                item.member = keep
                item.save(update_fields=["member"])
                add_count("group_meeting_attendance")
                continue
            existing.present = existing.present or item.present
            existing.save(update_fields=["present", "recorded_at"])
            item.delete()
            add_count("group_meeting_attendance_consolidated")

        registration_rank = {"CANCELLED": 0, "WAITLISTED": 1, "CONFIRMED": 2}
        for item in list(merged.event_registrations.select_for_update()):
            existing = keep.event_registrations.filter(schedule=item.schedule).first()
            if existing is None:
                item.member = keep
                item.save(update_fields=["member"])
                add_count("event_registrations")
                continue
            if registration_rank.get(item.status, 0) > registration_rank.get(existing.status, 0):
                existing.status = item.status
                existing.cancelled_at = item.cancelled_at
            existing.attended = existing.attended or item.attended
            existing.save(update_fields=["status", "cancelled_at", "attended"])
            item.delete()
            add_count("event_registrations_consolidated")

        # One attendance record per member/session is a hard database rule.
        # When both duplicates attended, consolidate corrections and retain the
        # strongest status and earliest check-in on the canonical record.
        attendance_rank = {"ABSENT": 0, "EXCUSED": 1, "LATE": 2, "PRESENT": 3}
        for item in list(merged.attendance_records.select_for_update()):
            existing = keep.attendance_records.filter(session=item.session).first()
            if existing is None:
                item.member = keep
                item.save(update_fields=["member"])
                add_count("attendance_records")
                continue
            item.corrections.update(record=existing)
            existing.checked_in_at = min(existing.checked_in_at, item.checked_in_at)
            if attendance_rank.get(item.status, 0) > attendance_rank.get(existing.status, 0):
                existing.status = item.status
            if item.checked_out_at and (not existing.checked_out_at or item.checked_out_at > existing.checked_out_at):
                existing.checked_out_at = item.checked_out_at
            existing.save(update_fields=["checked_in_at", "checked_out_at", "status"])
            item.delete()
            add_count("attendance_records_consolidated")

        # Follow-up milestones are unique. A completed touchpoint wins; notes,
        # assignee and reminder state are retained wherever the canonical row
        # does not already carry them.
        for item in list(merged.follow_ups.select_for_update()):
            existing = keep.follow_ups.filter(milestone=item.milestone).first()
            if existing is None:
                item.member = keep
                item.save(update_fields=["member"])
                add_count("follow_ups")
                continue
            existing.scheduled_for = min(existing.scheduled_for, item.scheduled_for)
            existing.completed_at = existing.completed_at or item.completed_at
            existing.assigned_to = existing.assigned_to or item.assigned_to
            existing.reminder_sent_at = existing.reminder_sent_at or item.reminder_sent_at
            if not existing.notes and item.notes:
                existing.notes = item.notes
            existing.save(update_fields=[
                "scheduled_for", "completed_at", "assigned_to",
                "reminder_sent_at", "notes", "updated_at",
            ])
            item.delete()
            add_count("follow_ups_consolidated")

        # One-to-one records need explicit collision behavior.
        merged_qr = related(merged, "qr_code")
        keep_qr = related(keep, "qr_code")
        if merged_qr and keep_qr is None:
            merged_qr.member = keep
            merged_qr.save(update_fields=["member"])
            add_count("qr_code")
        elif merged_qr:
            merged_qr.is_active = False
            merged_qr.save(update_fields=["is_active"])
            add_count("qr_code_deactivated")

        merged_metrics = related(merged, "engagement_metrics")
        keep_metrics = related(keep, "engagement_metrics")
        if merged_metrics and keep_metrics is None:
            merged_metrics.member = keep
            merged_metrics.save(update_fields=["member"])
            add_count("engagement_metrics")
        elif merged_metrics:
            merged_metrics.delete()
            add_count("engagement_metrics_consolidated")

        merged_preference = related(merged, "communication_preference")
        keep_preference = related(keep, "communication_preference")
        if merged_preference and keep_preference is None:
            merged_preference.member = keep
            merged_preference.save(update_fields=["member"])
            add_count("communication_preference")
        elif merged_preference:
            # Preserve the most restrictive choice across both identities.
            for field in ("email_enabled", "sms_enabled", "push_enabled", "announcements_enabled"):
                setattr(keep_preference, field, getattr(keep_preference, field) and getattr(merged_preference, field))
            keep_preference.save(update_fields=[
                "email_enabled", "sms_enabled", "push_enabled",
                "announcements_enabled", "updated_at",
            ])
            merged_preference.delete()
            add_count("communication_preference_consolidated")

        merged_profile = related(merged, "volunteer_profile")
        keep_profile = related(keep, "volunteer_profile")
        if merged_profile and keep_profile is None:
            merged_profile.member = keep
            merged_profile.save(update_fields=["member"])
            add_count("volunteer_profile")
        elif merged_profile:
            add_count("volunteer_assignments", merged_profile.assignments.update(volunteer=keep_profile))
            add_count("volunteer_availability", merged_profile.availability.update(volunteer=keep_profile))
            keep_profile.skills = sorted(set((keep_profile.skills or []) + (merged_profile.skills or [])))
            keep_profile.save(update_fields=["skills"])
            merged_profile.delete()
            add_count("volunteer_profile_consolidated")

        merged_origin = related(merged, "visitor_origin")
        keep_origin = related(keep, "visitor_origin")
        if merged_origin and keep_origin is None:
            merged_origin.converted_member = keep
            merged_origin.save(update_fields=["converted_member"])
            add_count("visitor_origin")
        elif merged_origin:
            # Both conversions are historical records and Visitor permits only
            # one origin per member. Retain the second link to the inactive
            # duplicate rather than destroying conversion history.
            add_count("visitor_origin_retained")

        merged.membership_status = MembershipStatus.INACTIVE
        merged.save(update_fields=["user", "membership_status", "updated_at"])

        MembershipHistory.objects.create(
            member=merged,
            previous_status=previous_status,
            new_status=MembershipStatus.INACTIVE,
            note=f"Merged into member {keep.id}",
            changed_by=changed_by,
        )

    return {"reassigned": reassigned}


def transfer_member(member, requesting_user, *, new_branch=None, new_fellowship=None, note=""):
    """
    Atomically move `member` to a new branch and/or fellowship, always
    leaving a MembershipHistory row behind (spec Phase 4: "preserve
    historical records", "no partial merge/transfer"). Authorization is
    the caller's job (see MemberViewSet.transfer) — this function only
    guarantees the write itself is transactional and audited.

    Returns the updated member. Raises ValueError for a no-op transfer
    (nothing actually changing) so the view can surface a clean 400
    instead of writing a pointless history row.
    """
    if new_branch is None and new_fellowship is None:
        raise ValueError("At least one of new_branch or new_fellowship is required.")

    previous_branch = member.branch
    previous_fellowship = member.fellowship

    # Explicit "clear the fellowship" support: caller passes new_fellowship=False.
    clearing_fellowship = new_fellowship is False and previous_fellowship is not None

    branch_changing = new_branch is not None and new_branch.id != previous_branch.id
    fellowship_changing = (
        new_fellowship is not None and new_fellowship is not False and (
            previous_fellowship is None or new_fellowship.id != previous_fellowship.id
        )
    )

    if not (branch_changing or fellowship_changing or clearing_fellowship):
        raise ValueError("Member is already in the requested branch/fellowship.")

    with transaction.atomic():
        if branch_changing:
            member.branch = new_branch
        if fellowship_changing:
            member.fellowship = new_fellowship
        elif clearing_fellowship:
            member.fellowship = None
        member.save(update_fields=["branch", "fellowship", "updated_at"])

        MembershipHistory.objects.create(
            member=member,
            previous_status=member.membership_status,
            new_status=member.membership_status,
            previous_branch=previous_branch,
            new_branch=member.branch,
            note=note or (
                f"Transferred fellowship from "
                f"{previous_fellowship.name if previous_fellowship else '(none)'} to "
                f"{member.fellowship.name if member.fellowship else '(none)'}."
                if fellowship_changing or clearing_fellowship else ""
            ),
            changed_by=requesting_user,
        )

    return member


def self_register_member(data):
    """
    The spec section 3 mandatory pipeline, in one atomic transaction:
    User account created -> Member record automatically created -> Member
    becomes available to Chapel. `data` role is always MEMBER — this path
    can never be used to create a privileged account (role isn't even an
    accepted field on RegisterSerializer).
    """
    from django.db import transaction

    from apps.accounts.models import User
    from apps.members.models import MemberQRCode
    from common.constants.roles import Roles

    with transaction.atomic():
        user = User.objects.create_user(
            email=data.get("email"),
            matric_no=data.get("matric_no"),
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone_number=data.get("phone_number", ""),
            branch=data["branch"],
            role=Roles.MEMBER,
        )

        member = Member.objects.create(
            user=user,
            branch=data["branch"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            gender=data.get("gender", ""),
            date_of_birth=data.get("date_of_birth"),
            email=data.get("email", "") or "",
            phone_number=data.get("phone_number", ""),
            college=data.get("college"),
            department=data.get("department"),
            community=data.get("community", ""),
            academic_level=data.get("academic_level", ""),
            membership_status=MembershipStatus.ACTIVE,
        )
        MemberQRCode.objects.get_or_create(member=member)

        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(AuditAction.MEMBER_SELF_REGISTER, "member", str(member.id), user=user)

    return user
