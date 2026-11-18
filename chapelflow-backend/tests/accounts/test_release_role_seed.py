import pytest

from apps.accounts.models import RolePermission
from common.constants.roles import PermissionCodes, Roles
from scripts.seed_roles import seed_roles


@pytest.mark.django_db
def test_release_role_seed_is_idempotent_and_grants_chapel_admin_access():
    seed_roles()
    before = RolePermission.objects.count()
    seed_roles()

    assert RolePermission.objects.count() == before
    assert RolePermission.objects.filter(
        legacy_role_code=Roles.CHAPEL_ADMIN,
        permission__code=PermissionCodes.MEMBERS_VIEW,
    ).exists()
