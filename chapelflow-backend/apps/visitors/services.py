from django.db import transaction
from django.utils import timezone

from .models import Visitor, VisitorStatus


def find_duplicate_visitors(queryset):
    """
    Conservative duplicate detection (spec Phase 5: "detect likely
    duplicates... do not automatically merge uncertain matches").
    Mirrors apps.members.services.find_duplicate_members's approach:
    group by normalized (name, contact) within the caller's own
    (already branch-scoped) queryset, and only flag a pair when they
    share a real contact point — never on name alone, which is far too
    prone to false positives for a public, self-submitted form.
    """
    from collections import defaultdict

    buckets = defaultdict(list)
    for visitor in queryset.values("id", "full_name", "email", "phone_number", "created_at"):
        full_name, email, phone_number, created_at = (
            visitor["full_name"], visitor["email"], visitor["phone_number"], visitor["created_at"]
        )
        key = (full_name.strip().lower(), (email or "").strip().lower() or (phone_number or "").strip())
        if key[1]:
            buckets[key].append(visitor)

    return [
        {
            "candidates": [
                {"id": str(v["id"]), "full_name": v["full_name"], "created_at": v["created_at"]} for v in visitors
            ],
            "matched_on": {"full_name": key[0], "contact": key[1]},
        }
        for key, visitors in buckets.items()
        if len(visitors) > 1
    ]


def visitor_analytics(queryset):
    """
    Spec Phase 5: first-time visitors, returning visitors, conversions,
    conversion rate, follow-up completion — computed over the caller's
    (already branch-scoped) queryset so a Fellowship/Branch admin only
    ever sees their own numbers.
    """
    from django.db.models import Count, Q

    total = queryset.count()
    if total == 0:
        return {
            "total_visitors": 0, "first_time_visitors": 0, "returning_visitors": 0,
            "converted": 0, "conversion_rate": 0.0,
            "follow_ups_total": 0, "follow_ups_completed": 0, "follow_up_completion_rate": 0.0,
        }

    # "Returning" = has more than one linked attendance_records row
    # (apps.attendance.VisitorAttendance.visitor_record) — i.e. they
    # showed up more than once, not just submitted the form once.
    returning = queryset.annotate(visit_count=Count("attendance_records")).filter(visit_count__gt=1).count()
    converted = queryset.filter(status=VisitorStatus.REGISTERED).count()

    from .models import VisitorFollowUp
    follow_ups = VisitorFollowUp.objects.filter(visitor__in=queryset)
    follow_ups_total = follow_ups.count()
    follow_ups_completed = follow_ups.exclude(outcome=VisitorFollowUp.Outcome.PENDING).count()

    return {
        "total_visitors": total,
        "first_time_visitors": total - returning,
        "returning_visitors": returning,
        "converted": converted,
        "conversion_rate": round(converted / total * 100, 1),
        "follow_ups_total": follow_ups_total,
        "follow_ups_completed": follow_ups_completed,
        "follow_up_completion_rate": (
            round(follow_ups_completed / follow_ups_total * 100, 1) if follow_ups_total else 0.0
        ),
    }


def convert_visitor_to_member(visitor: Visitor, extra_member_fields: dict, changed_by):
    """
    Optional Full Registration step (spec section 4): Visitor -> Member.
    This is a STAFF-ASSISTED conversion (e.g. a Fellowship Leader helping
    a first-timer register in person) and is intentionally separate from
    apps.members.services.self_register_member, which is the public
    self-service path and creates a User+Member together. A
    staff-assisted conversion here creates a Member WITHOUT a login by
    default (extra_member_fields may include `user` if the visitor also
    wants an account) — a Member row has never required a User (see
    apps.members.models.Member docstring).
    """
    if visitor.converted_member_id:
        raise ValueError("This visitor has already been converted to a member.")

    from apps.members.models import Member, MemberQRCode, MembershipStatus

    with transaction.atomic():
        member = Member.objects.create(
            branch=visitor.branch,
            first_name=extra_member_fields.get("first_name") or visitor.full_name.split(" ", 1)[0],
            last_name=extra_member_fields.get("last_name") or (
                visitor.full_name.split(" ", 1)[1] if " " in visitor.full_name else ""
            ),
            gender=visitor.gender,
            email=visitor.email,
            phone_number=visitor.phone_number,
            address=visitor.address,
            college=extra_member_fields.get("college"),
            department=extra_member_fields.get("department"),
            community=extra_member_fields.get("community", ""),
            membership_status=MembershipStatus.ACTIVE,
            membership_date=timezone.now().date(),
        )
        MemberQRCode.objects.get_or_create(member=member)

        visitor.converted_member = member
        visitor.status = VisitorStatus.REGISTERED
        visitor.converted_at = timezone.now()
        visitor.save(update_fields=["converted_member", "status", "converted_at"])

        from apps.audit.services import write_audit_log
        from apps.audit.models import AuditAction
        write_audit_log(
            AuditAction.CREATE, "member", str(member.id), user=changed_by,
            metadata={"converted_from_visitor_id": str(visitor.id)},
        )

    return member
