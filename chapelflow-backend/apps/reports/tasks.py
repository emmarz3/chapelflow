import logging
import tempfile

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def _is_retryable_report_error(exc):
    from django.db import DatabaseError

    try:
        import requests
    except ImportError:
        requests_error = ()
    else:
        requests_error = requests.RequestException
    return isinstance(exc, (DatabaseError, OSError, TimeoutError, requests_error))


@shared_task(bind=True, max_retries=3, default_retry_delay=30, retry_backoff=True, retry_jitter=True, acks_late=True, reject_on_worker_lost=True, soft_time_limit=1740, time_limit=1800)
def run_report_job(self, job_id):
    """
    Phase 3 Security: Re-validates that requested_by user still has
    permission to access the report's branch at execution time.
    """
    from .models import ReportJob, ReportJobStatus
    from .services import REPORT_GENERATORS, write_report_export
    from common.permissions.scoping import user_can_access_branch

    with transaction.atomic():
        job = ReportJob.objects.select_for_update().get(id=job_id)
        if job.status == ReportJobStatus.COMPLETE and job.file_url:
            return {"status": "skipped", "reason": "already complete"}
        job.status = ReportJobStatus.RUNNING
        job.progress = 0
        job.rows_processed = 0
        job.error_message = ""
        job.save(update_fields=["status", "progress", "rows_processed", "error_message"])
    job = ReportJob.objects.select_related("branch", "requested_by").get(id=job_id)
    
    # Phase 3: Re-validate authorization before generating report
    if not job.requested_by_id or not user_can_access_branch(job.requested_by, job.branch.id):
        logger.warning(
            f"run_report_job: User {job.requested_by_id} "
            f"no longer has access to branch {job.branch.id} - task aborted"
        )
        job.status = ReportJobStatus.FAILED
        job.error_message = "Permission denied - you no longer have access to this branch"
        job.save(update_fields=["status", "error_message"])
        return
    
    try:
        generator = REPORT_GENERATORS.get(job.report_type)
        if not generator:
            raise ValueError(f"No generator registered for report type {job.report_type}")

        rows = generator(job.branch, job.filters or {})
        if hasattr(rows, "count") and callable(rows.count):
            total_rows = rows.count()
            rows = rows.iterator(chunk_size=2000) if hasattr(rows, "iterator") else rows
        else:
            total_rows = None

        # Spec section 16: "Do not claim Excel/PDF support if the task
        # actually only generates CSV." export_report_rows dispatches to
        # the real per-format serializer for job.export_format instead of
        # hardcoding CSV regardless of what was requested.
        title = f"{job.get_report_type_display()} Report — {job.branch.name}"
        from apps.uploads.storage import get_storage_service
        storage = get_storage_service()
        with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b") as output:
            def update_progress(row_count):
                job.rows_processed = row_count
                job.progress = min(95, int(row_count * 95 / total_rows)) if total_rows else 0
                job.save(update_fields=["rows_processed", "progress"])

            content_type, extension, row_count = write_report_export(
                job.export_format, rows, output, title=title, on_progress=update_progress,
            )
            job.rows_processed = row_count
            job.progress = 95
            job.save(update_fields=["rows_processed", "progress"])
            file_url = storage.upload_fileobj(
                output,
                filename=f"reports/{job.report_type.lower()}_{job.id}.{extension}",
                content_type=content_type,
            )

        job.file_url = file_url
        job.status = ReportJobStatus.COMPLETE
        job.progress = 100
        job.completed_at = timezone.now()
        job.save(update_fields=["file_url", "status", "progress", "completed_at"])
    except Exception as exc:
        if _is_retryable_report_error(exc) and self.request.retries < self.max_retries:
            job.status = ReportJobStatus.QUEUED
            job.error_message = "Report generation failed temporarily; retrying."
            job.save(update_fields=["status", "error_message"])
            raise self.retry(exc=exc)
        job.status = ReportJobStatus.FAILED
        job.error_message = str(exc)[:500]
        job.save(update_fields=["status", "error_message"])
        raise
