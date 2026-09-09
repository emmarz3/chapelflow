import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def run_report_job(job_id):
    """
    Phase 3 Security: Re-validates that requested_by user still has
    permission to access the report's branch at execution time.
    """
    from .models import ReportJob, ReportJobStatus
    from .services import REPORT_GENERATORS, export_report_rows
    from common.permissions.scoping import user_can_access_branch

    job = ReportJob.objects.select_related("branch", "requested_by").get(id=job_id)
    
    # Phase 3: Re-validate authorization before generating report
    if not user_can_access_branch(job.requested_by, job.branch.id):
        logger.warning(
            f"run_report_job: User {job.requested_by.id} ({job.requested_by.email}) "
            f"no longer has access to branch {job.branch.id} - task aborted"
        )
        job.status = ReportJobStatus.FAILED
        job.error_message = "Permission denied - you no longer have access to this branch"
        job.save(update_fields=["status", "error_message"])
        return
    
    job.status = ReportJobStatus.RUNNING
    job.save(update_fields=["status"])

    try:
        generator = REPORT_GENERATORS.get(job.report_type)
        if not generator:
            raise ValueError(f"No generator registered for report type {job.report_type}")

        rows = list(generator(job.branch, job.filters or {}))

        # Spec section 16: "Do not claim Excel/PDF support if the task
        # actually only generates CSV." export_report_rows dispatches to
        # the real per-format serializer for job.export_format instead of
        # hardcoding CSV regardless of what was requested.
        title = f"{job.get_report_type_display()} Report — {job.branch.name}"
        content, content_type, extension = export_report_rows(job.export_format, rows, title=title)

        from apps.uploads.storage import get_storage_service
        storage = get_storage_service()
        file_url = storage.upload_bytes(
            content,
            filename=f"reports/{job.report_type.lower()}_{job.id}.{extension}",
            content_type=content_type,
        )

        job.file_url = file_url
        job.status = ReportJobStatus.COMPLETE
        job.completed_at = timezone.now()
        job.save(update_fields=["file_url", "status", "completed_at"])
    except Exception as exc:
        job.status = ReportJobStatus.FAILED
        job.error_message = str(exc)[:500]
        job.save(update_fields=["status", "error_message"])
        raise
