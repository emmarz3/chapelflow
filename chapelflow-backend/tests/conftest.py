import pytest
from rest_framework.test import APIClient

from apps.organizations.models import Branch, Organization
from common.constants.roles import PermissionCodes, Roles


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Run the canonical role->permission grants (scripts/seed_roles.py) once
    against the test database, right after migrations apply. Many test
    files create privileged-role users assuming they already have the
    permissions that role has in a real deployment, but nothing seeds
    RolePermission rows by default -- without this, every one of those
    checks fails closed with 403 regardless of the role's intended access.
    """
    with django_db_blocker.unblock():
        from scripts.seed_roles import seed_roles
        seed_roles()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Test Org", slug="test-org")


@pytest.fixture
def branch_a(db, organization):
    return Branch.objects.create(organization=organization, name="Branch A", branch_type="CHAPEL")


@pytest.fixture
def branch_b(db, organization):
    return Branch.objects.create(organization=organization, name="Branch B", branch_type="CHAPEL")


@pytest.fixture
def organization_2(db):
    """A second, unrelated Organization -- for proving org-wide (Chaplain) scope still stops at org boundaries."""
    return Organization.objects.create(name="Other Org", slug="other-org")


@pytest.fixture
def branch_org2(db, organization_2):
    return Branch.objects.create(organization=organization_2, name="Other Org Branch", branch_type="CHAPEL")


@pytest.fixture
def seed_member_permissions(db):
    """Grants CHAPEL_ADMIN the permission codes needed across the test suite."""
    from apps.accounts.models import Permission, RolePermission

    codes = [
        PermissionCodes.MEMBERS_VIEW, PermissionCodes.MEMBERS_CREATE,
        PermissionCodes.MEMBERS_UPDATE, PermissionCodes.MEMBERS_DELETE,
        PermissionCodes.MEMBERS_IMPORT, PermissionCodes.ATTENDANCE_VIEW,
        PermissionCodes.ATTENDANCE_CREATE, PermissionCodes.EVENTS_VIEW,
        PermissionCodes.EVENTS_CREATE, PermissionCodes.EVENTS_UPDATE,
        PermissionCodes.EVENTS_DELETE, PermissionCodes.REPORTS_VIEW,
        PermissionCodes.REPORTS_EXPORT,
    ]
    for code in codes:
        perm, _ = Permission.objects.get_or_create(code=code)
        RolePermission.objects.get_or_create(legacy_role_code=Roles.CHAPEL_ADMIN, permission=perm)
    return codes


@pytest.fixture
def chapel_admin_a(db, branch_a):
    from apps.accounts.models import User
    return User.objects.create_user(email="admin_a@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_a)


@pytest.fixture
def chapel_admin_b(db, branch_b):
    from apps.accounts.models import User
    return User.objects.create_user(email="admin_b@test.com", password="Pass12345!", role=Roles.CHAPEL_ADMIN, branch=branch_b)


@pytest.fixture
def finance_user(db, branch_a):
    from apps.accounts.models import User
    return User.objects.create_user(email="finance@test.com", password="Pass12345!", role=Roles.FINANCE_OFFICER, branch=branch_a)


@pytest.fixture
def super_admin(db):
    from apps.accounts.models import User
    return User.objects.create_superuser(email="super@test.com", password="Pass12345!")


@pytest.fixture
def member_in_branch_a(db, branch_a):
    from apps.accounts.models import User
    from apps.members.models import Member, MemberQRCode

    user = User.objects.create_user(matric_no="SWE/2024/005", password="Pass12345!", role=Roles.MEMBER, branch=branch_a)
    member = Member.objects.create(user=user, branch=branch_a, first_name="Ada", last_name="Lovelace")
    MemberQRCode.objects.get_or_create(member=member)
    return member


@pytest.fixture
def make_user(db):
    from apps.accounts.models import User

    def _make(**kwargs):
        password = kwargs.pop("password", "Pass12345!")
        kwargs.setdefault("role", Roles.MEMBER)
        return User.objects.create_user(password=password, **kwargs)

    return _make
