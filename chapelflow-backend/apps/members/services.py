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
    from django.db import transaction

    reassigned = {}
    with transaction.atomic():
        # Phase 4: Comprehensive relationship reassignment
        # FK relationships using reverse manager
        fk_relationships = [
            "group_memberships",  # existing
            "tags",               # existing
        ]
        
        # Phase 4: Add conditional relationships based on installed apps
        # Event registrations
        if hasattr(merged, 'event_registrations'):
            fk_relationships.append('event_registrations')
        
        # Attendance records
        if hasattr(merged, 'attendance_records'):
            fk_relationships.append('attendance_records')
        
        # Visitor attendance (if member was visitor who converted)
        if hasattr(merged, 'visitor_attendances'):
            fk_relationships.append('visitor_attendances')
        
        # Pastoral cases
        if hasattr(merged, 'pastoral_cases'):
            fk_relationships.append('pastoral_cases')
        
        # Prayer requests
        if hasattr(merged, 'prayer_requests'):
            fk_relationships.append('prayer_requests')
        
        # Giving records
        if hasattr(merged, 'giving_records'):
            fk_relationships.append('giving_records')
        
        # Pledges
        if hasattr(merged, 'pledges'):
            fk_relationships.append('pledges')
        
        # Notifications
        if hasattr(merged, 'notifications'):
            fk_relationships.append('notifications')
        
        # Phase 11: Follow-ups
        if hasattr(merged, 'follow_ups'):
            fk_relationships.append('follow_ups')
        
        # Reassign all FK relationships
        for related_name in fk_relationships:
            manager = getattr(merged, related_name, None)
            if manager is None:
                continue
            count = manager.all().update(member=keep)
            if count:
                reassigned[related_name] = count

        # volunteer_profile is a OneToOne, not a reverse-FK manager, so it
        # needs its own attribute-error-safe handling.
        try:
            vp = merged.volunteer_profile
        except Exception:  # noqa: BLE001 - RelatedObjectDoesNotExist, not worth importing
            vp = None
        if vp is not None and not hasattr(keep, "volunteer_profile"):
            vp.member = keep
            vp.save(update_fields=["member"])
            reassigned["volunteer_profile"] = 1
        
        # Phase 11: engagement_metrics is a OneToOne relationship
        # If merged has metrics and keep doesn't, reassign
        # If both have metrics, delete merged's (keep's takes precedence)
        try:
            merged_metrics = merged.engagement_metrics
        except Exception:  # noqa: BLE001 - RelatedObjectDoesNotExist
            merged_metrics = None
        
        if merged_metrics is not None:
            try:
                keep_metrics = keep.engagement_metrics
                # Both exist - delete merged's metrics (keep's are authoritative)
                merged_metrics.delete()
                reassigned["engagement_metrics_deleted"] = 1
            except Exception:  # noqa: BLE001 - keep has no metrics
                # Only merged has metrics - reassign to keep
                merged_metrics.member = keep
                merged_metrics.save()
                reassigned["engagement_metrics"] = 1

        merged.membership_status = MembershipStatus.INACTIVE
        merged.save(update_fields=["membership_status"])

        MembershipHistory.objects.create(
            member=merged, previous_status=merged.membership_status,
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
            membership_status=MembershipStatus.ACTIVE,
        )
        MemberQRCode.objects.get_or_create(member=member)

        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(AuditAction.MEMBER_SELF_REGISTER, "member", str(member.id), user=user)

    return user
