import uuid

from django.conf import settings
from django.db import models


class ReportExportFormat(models.TextChoices):
    CSV = "CSV", "CSV"
    EXCEL = "EXCEL", "Excel"
    PDF = "PDF", "PDF"


class ReportJobStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    RUNNING = "RUNNING", "Running"
    COMPLETE = "COMPLETE", "Complete"
    FAILED = "FAILED", "Failed"


class ReportJob(models.Model):
    """
    Large reports are never generated synchronously in a request. A job
    row is created immediately (202 Accepted returned to the client), a
    Celery task does the work, and the client polls/receives a notification.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, related_name="report_jobs")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    report_type = models.CharField(
        max_length=30,
        choices=[
            ("MEMBERSHIP", "Membership"), ("ATTENDANCE", "Attendance"), ("EVENTS", "Events"),
            ("VISITORS", "Visitors"), ("GIVING", "Giving"), ("MINISTRIES", "Ministries"),
            ("VOLUNTEERS", "Volunteers"),
        ],
    )
    export_format = models.CharField(max_length=10, choices=ReportExportFormat.choices, default=ReportExportFormat.CSV)
    filters = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=ReportJobStatus.choices, default=ReportJobStatus.QUEUED)
    file_url = models.URLField(blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "reports_job"
