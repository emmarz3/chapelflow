import logging

from common.middleware.audit_middleware import get_current_audit_context
from .models import AuditLog

logger = logging.getLogger("chapelflow.audit")


def write_audit_log(action, resource_type, resource_id="", metadata=None, user=None):
    """
    Central entry point for audit logging. Prefer calling this explicitly
    from sensitive views/services (login, role change, financial action,
    pastoral/member record access) rather than relying purely on signals,
    since signals can't distinguish *why* a record was touched.
    """
    ctx = get_current_audit_context()
    entry_user = user if user is not None else ctx.get("user")
    entry_user = entry_user if getattr(entry_user, "is_authenticated", False) else None

    AuditLog.objects.create(
        user=entry_user,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        metadata=metadata or {},
        ip_address=ctx.get("ip_address"),
        user_agent=(ctx.get("user_agent") or "")[:255],
    )
    logger.info("audit action=%s resource=%s:%s user=%s", action, resource_type, resource_id, entry_user)
