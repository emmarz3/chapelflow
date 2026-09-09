"""
Report generation services. Each function returns a queryset/aggregate
dict; the Celery task (tasks.py) handles serializing to CSV/Excel/PDF and
uploading via apps.uploads.storage.
"""
from django.db.models import Count, Sum, Max, Min, Q


def membership_report(branch, filters):
    from apps.members.models import Member
    qs = Member.objects.filter(branch=branch)
    if filters.get("membership_status"):
        qs = qs.filter(membership_status=filters["membership_status"])
    return qs.values("membership_status").annotate(count=Count("id"))


def attendance_report(branch, filters):
    from apps.attendance.models import AttendanceRecord
    qs = AttendanceRecord.objects.filter(session__branch=branch)
    if filters.get("date_from"):
        qs = qs.filter(checked_in_at__gte=filters["date_from"])
    if filters.get("date_to"):
        qs = qs.filter(checked_in_at__lte=filters["date_to"])
    if filters.get("event_id"):
        qs = qs.filter(session__event_schedule__event_id=filters["event_id"])
    return qs.values("session__id", "method").annotate(count=Count("id"))


def giving_report(branch, filters):
    from apps.finance.models import Giving
    qs = Giving.objects.filter(branch=branch)
    if filters.get("date_from"):
        qs = qs.filter(given_at__gte=filters["date_from"])
    if filters.get("date_to"):
        qs = qs.filter(given_at__lte=filters["date_to"])
    if filters.get("category_id"):
        qs = qs.filter(category_id=filters["category_id"])
    return qs.values("category__name").annotate(total=Sum("amount"), count=Count("id"))


def events_report(branch, filters):
    """
    Phase 15: Events report generator.
    
    Generates report on events with attendance statistics:
    - Event name, date, type
    - Total attendance count
    - Unique attendees
    - Event category breakdown
    
    Filters:
    - date_from/date_to: Filter by event date
    - event_type: Filter by event type
    - category_id: Filter by event category
    """
    from apps.events.models import Event
    from apps.attendance.models import AttendanceSession
    from django.db.models import Q
    
    qs = Event.objects.filter(branch=branch)
    
    # Apply filters
    if filters.get("date_from"):
        qs = qs.filter(schedules__start_time__gte=filters["date_from"])
    if filters.get("date_to"):
        qs = qs.filter(schedules__start_time__lte=filters["date_to"])
    if filters.get("event_type"):
        qs = qs.filter(event_type=filters["event_type"])
    if filters.get("category_id"):
        qs = qs.filter(category_id=filters["category_id"])
    
    # Aggregate attendance data
    return qs.values(
        "id", "name", "event_type", "category__name"
    ).annotate(
        total_schedules=Count("schedules", distinct=True),
        total_attendance=Count("schedules__attendance_sessions__records", distinct=True)
    )


def visitors_report(branch, filters):
    """
    Phase 15: Visitors report generator.
    
    Generates report on visitor attendance and follow-up:
    - Visitor name, contact info
    - First visit date
    - Total visits
    - Last visit date
    - Follow-up status
    
    Filters:
    - date_from/date_to: Filter by visit date
    - follow_up_status: Filter by follow-up completion
    - visit_count_min: Minimum visit count
    """
    from apps.visitors.models import Visitor
    from apps.attendance.models import VisitorAttendance
    from django.db.models import Min, Max
    
    qs = Visitor.objects.filter(branch=branch)
    
    # Annotate with attendance stats
    qs = qs.annotate(
        first_visit=Min("visitor_attendance__checked_in_at"),
        last_visit=Max("visitor_attendance__checked_in_at"),
        visit_count=Count("visitor_attendance", distinct=True)
    )
    
    # Apply filters
    if filters.get("date_from"):
        qs = qs.filter(first_visit__gte=filters["date_from"])
    if filters.get("date_to"):
        qs = qs.filter(last_visit__lte=filters["date_to"])
    if filters.get("visit_count_min"):
        qs = qs.filter(visit_count__gte=filters["visit_count_min"])
    
    # Return visitor data with follow-up info
    return qs.values(
        "id", "first_name", "last_name", "email", "phone_number",
        "first_visit", "last_visit", "visit_count"
    ).annotate(
        follow_ups_count=Count("follow_ups", distinct=True),
        follow_ups_completed=Count("follow_ups", filter=Q(follow_ups__completed_at__isnull=False), distinct=True)
    )


def ministries_report(branch, filters):
    """
    Phase 15: Ministries report generator.
    
    Generates report on ministry groups and membership:
    - Ministry name, type
    - Total members
    - Active vs inactive members
    - Leader information
    
    Filters:
    - group_type: Filter by ministry type
    - is_active: Filter active/inactive ministries
    """
    from apps.groups.models import Group, GroupType
    
    qs = Group.objects.filter(
        branch=branch,
        group_type=GroupType.MINISTRY
    )
    
    # Apply filters
    if filters.get("is_active") is not None:
        qs = qs.filter(is_active=filters["is_active"])
    
    # Aggregate membership data
    return qs.values(
        "id", "name", "description", "leader__first_name", "leader__last_name", "is_active"
    ).annotate(
        total_members=Count("memberships", distinct=True),
        active_members=Count("memberships", filter=Q(memberships__is_active=True), distinct=True)
    )


def volunteers_report(branch, filters):
    """
    Phase 15: Volunteers report generator.
    
    Generates report on volunteer assignments and activity:
    - Volunteer name
    - Total assignments
    - Completed assignments
    - Active assignments
    - Last volunteered date
    
    Filters:
    - date_from/date_to: Filter by assignment date
    - status: Filter by assignment status
    - ministry_id: Filter by specific ministry
    """
    from apps.volunteers.models import VolunteerAssignment
    from django.db.models import Q
    
    qs = VolunteerAssignment.objects.filter(branch=branch).select_related("volunteer", "schedule")
    
    # Apply filters
    if filters.get("date_from"):
        qs = qs.filter(schedule__start_time__gte=filters["date_from"])
    if filters.get("date_to"):
        qs = qs.filter(schedule__end_time__lte=filters["date_to"])
    if filters.get("status"):
        qs = qs.filter(status=filters["status"])
    if filters.get("ministry_id"):
        qs = qs.filter(schedule__ministry_id=filters["ministry_id"])
    
    # Group by volunteer and aggregate
    return qs.values(
        "volunteer__id", 
        "volunteer__member__first_name",
        "volunteer__member__last_name",
        "volunteer__member__email"
    ).annotate(
        total_assignments=Count("id", distinct=True),
        completed_assignments=Count("id", filter=Q(status="COMPLETED"), distinct=True),
        active_assignments=Count("id", filter=Q(status="CONFIRMED"), distinct=True),
        last_assignment_date=Max("schedule__start_time")
    )


REPORT_GENERATORS = {
    "MEMBERSHIP": membership_report,
    "ATTENDANCE": attendance_report,
    "GIVING": giving_report,
    "EVENTS": events_report,
    "VISITORS": visitors_report,
    "MINISTRIES": ministries_report,
    "VOLUNTEERS": volunteers_report,
}


# --------------------------------------------------------------------------
# Export engine (spec section 16): "Do not claim Excel/PDF support if the
# task actually only generates CSV." This used to be true here — export_format
# existed on ReportJob but tasks.py always wrote CSV regardless of what was
# selected. These three functions are the real per-format serializers;
# apps.reports.tasks.run_report_job dispatches to the one matching
# job.export_format instead of hardcoding CSV.
# --------------------------------------------------------------------------

def sanitize_csv_value(value):
    """
    Phase 15: Sanitize CSV values to prevent formula injection.
    
    Excel/LibreOffice interpret cells starting with =, +, -, @, tab, or carriage return
    as formulas. Attackers can inject =cmd|'/c calc'!A1 or similar to execute code
    when the CSV is opened.
    
    Mitigation:
    - Prepend single quote (') to values starting with dangerous characters
    - The quote makes Excel treat it as text, not a formula
    - Preserves the original value for human reading
    
    References:
    - OWASP CSV Injection: https://owasp.org/www-community/attacks/CSV_Injection
    - CWE-1236: Improper Neutralization of Formula Elements in a CSV File
    """
    if value is None:
        return ""
    
    # Convert to string
    str_value = str(value)
    
    # Check if starts with dangerous characters
    dangerous_prefixes = ('=', '+', '-', '@', '\t', '\r', '\n')
    
    if str_value and str_value[0] in dangerous_prefixes:
        # Prepend single quote to neutralize formula
        return f"'{str_value}"
    
    return str_value


def export_rows_csv(rows: list) -> bytes:
    import csv
    import io

    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        
        # Phase 15: Sanitize each row to prevent CSV formula injection
        sanitized_rows = [
            {key: sanitize_csv_value(value) for key, value in row.items()}
            for row in rows
        ]
        
        writer.writerows(sanitized_rows)
    return buffer.getvalue().encode("utf-8")


def export_rows_excel(rows: list) -> bytes:
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Report"

    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            # Stringify anything openpyxl can't natively write (e.g. UUID,
            # Decimal is fine, but keep this defensive since report rows
            # come from arbitrary values(...).annotate(...) querysets).
            ws.append([v if isinstance(v, (int, float, str, type(None))) else str(v) for v in row.values()])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def export_rows_pdf(rows: list, title: str = "Report") -> bytes:
    import io

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    if rows:
        headers = list(rows[0].keys())
        data = [headers] + [[str(row.get(h, "")) for h in headers] for row in rows]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No data for the selected filters.", styles["Normal"]))

    doc.build(elements)
    return buffer.getvalue()


REPORT_EXPORTERS = {
    "CSV": {
        "func": export_rows_csv,
        "content_type": "text/csv",
        "extension": "csv",
    },
    "EXCEL": {
        "func": export_rows_excel,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "extension": "xlsx",
    },
    "PDF": {
        "func": export_rows_pdf,
        "content_type": "application/pdf",
        "extension": "pdf",
    },
}


def export_report_rows(export_format: str, rows: list, title: str = "Report") -> tuple:
    """
    Dispatches to the right exporter above for `export_format`
    (ReportJob.export_format: CSV/EXCEL/PDF). Returns
    (bytes, content_type, file_extension). Raises ValueError for an
    unrecognized format rather than silently falling back to CSV — a
    silent fallback is exactly the "claims a format it doesn't support"
    problem this was written to fix.
    """
    config = REPORT_EXPORTERS.get(export_format)
    if not config:
        raise ValueError(f"Unsupported export_format: {export_format!r}")

    if export_format == "PDF":
        content = config["func"](rows, title=title)
    else:
        content = config["func"](rows)

    return content, config["content_type"], config["extension"]
