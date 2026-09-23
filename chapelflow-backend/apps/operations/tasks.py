import json

from celery import shared_task
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import write_audit_log

from .models import ContentEntry, ContentRevision, ContentStatus
from .serializers import ContentEntrySerializer


@shared_task
def publish_scheduled_content():
    """Publish approved content whose scheduled release time has arrived."""
    published = 0
    now = timezone.now()
    with transaction.atomic():
        entries = list(
            ContentEntry.objects.select_for_update().filter(
                status=ContentStatus.SCHEDULED,
                publish_at__isnull=False,
                publish_at__lte=now,
            )
        )
        for entry in entries:
            entry.status = ContentStatus.PUBLISHED
            entry.published_at = now
            entry.save(update_fields=["status", "published_at", "updated_at"])
            latest = entry.revisions.aggregate(value=Max("version"))["value"] or 0
            ContentRevision.objects.create(
                content=entry,
                version=latest + 1,
                snapshot=json.loads(
                    json.dumps(ContentEntrySerializer(entry).data, cls=DjangoJSONEncoder)
                ),
            )
            write_audit_log(
                AuditAction.UPDATE,
                "operations.content",
                entry.id,
                metadata={"status": ContentStatus.PUBLISHED, "scheduled": True},
            )
            published += 1
    return {"published": published}
