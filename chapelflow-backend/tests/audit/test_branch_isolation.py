import pytest


@pytest.mark.django_db
class TestAuditLogBranchIsolation:
    """
    Phase 1 fix regression tests: AuditLogViewSet previously returned
    every branch's audit trail to anyone with AUDIT_VIEW, including
    CHAPEL_ADMIN (a branch-scoped role that holds this permission by
    default -- see scripts/seed_roles.py). Scoped by the acting user's
    branch (AuditLog has no branch FK of its own, only `user`).
    """

    def _grant_audit_view(self, role):
        from apps.accounts.models import Permission, RolePermission
        from common.constants.roles import PermissionCodes

        perm, _ = Permission.objects.get_or_create(code=PermissionCodes.AUDIT_VIEW)
        RolePermission.objects.get_or_create(legacy_role_code=role, permission=perm)

    def test_chapel_admin_cannot_see_another_branchs_audit_entries(
        self, api_client, chapel_admin_a, chapel_admin_b
    ):
        from apps.audit.models import AuditAction, AuditLog
        from common.constants.roles import Roles

        self._grant_audit_view(Roles.CHAPEL_ADMIN)
        entry_b = AuditLog.objects.create(
            user=chapel_admin_b, action=AuditAction.LOGIN, resource_type="session", resource_id="1",
        )

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/audit/logs/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert str(entry_b.id) not in ids

    def test_chapel_admin_cannot_fetch_another_branchs_audit_entry_by_id(
        self, api_client, chapel_admin_a, chapel_admin_b
    ):
        from apps.audit.models import AuditAction, AuditLog
        from common.constants.roles import Roles

        self._grant_audit_view(Roles.CHAPEL_ADMIN)
        entry_b = AuditLog.objects.create(
            user=chapel_admin_b, action=AuditAction.MFA_RESET, resource_type="user", resource_id="1",
        )

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get(f"/api/v1/audit/logs/{entry_b.id}/")
        # Must be 404, not 403 -- matches this codebase's direct-ID convention.
        assert response.status_code == 404

    def test_chapel_admin_sees_own_branchs_audit_entries(self, api_client, chapel_admin_a):
        from apps.audit.models import AuditAction, AuditLog
        from common.constants.roles import Roles

        self._grant_audit_view(Roles.CHAPEL_ADMIN)
        entry_a = AuditLog.objects.create(
            user=chapel_admin_a, action=AuditAction.LOGIN, resource_type="session", resource_id="1",
        )

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/audit/logs/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert str(entry_a.id) in ids

    def test_super_admin_sees_every_branchs_audit_entries(
        self, api_client, super_admin, chapel_admin_a, chapel_admin_b
    ):
        from apps.audit.models import AuditAction, AuditLog

        entry_a = AuditLog.objects.create(user=chapel_admin_a, action=AuditAction.LOGIN, resource_type="session", resource_id="1")
        entry_b = AuditLog.objects.create(user=chapel_admin_b, action=AuditAction.LOGIN, resource_type="session", resource_id="2")

        api_client.force_authenticate(user=super_admin)
        response = api_client.get("/api/v1/audit/logs/")
        assert response.status_code == 200
        ids = {row["id"] for row in response.data["data"]}
        assert str(entry_a.id) in ids
        assert str(entry_b.id) in ids

    def test_audit_log_entry_with_no_user_is_invisible_to_branch_scoped_admin(
        self, api_client, chapel_admin_a
    ):
        """System-generated entries with user=None fail closed for branch-scoped roles rather than leaking."""
        from apps.audit.models import AuditAction, AuditLog
        from common.constants.roles import Roles

        self._grant_audit_view(Roles.CHAPEL_ADMIN)
        AuditLog.objects.create(user=None, action=AuditAction.LOGIN, resource_type="session", resource_id="orphan")

        api_client.force_authenticate(user=chapel_admin_a)
        response = api_client.get("/api/v1/audit/logs/")
        assert response.status_code == 200
        assert response.data["data"] == []
