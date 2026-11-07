import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import Member
from apps.ministries.models import Group, GroupType
from apps.organizations.models import Branch, Organization
from common.constants.roles import Roles


@pytest.mark.django_db
def test_leader_operations_exposes_only_assigned_group():
    organization = Organization.objects.create(name="Chrisland", slug="chrisland-operations")
    branch = Branch.objects.create(name="Chapel", organization=organization, branch_type="CHAPEL")
    assigned = Group.objects.create(branch=branch, name="Choir Unit", group_type=GroupType.UNIT)
    other = Group.objects.create(branch=branch, name="Drama Unit", group_type=GroupType.UNIT)
    leader = User.objects.create_user(
        email="unit.leader@example.test", password="Pass12345!", role=Roles.UNIT_HEAD,
        branch=branch, institutional_group=assigned,
    )
    student_user = User.objects.create_user(
        email="student@example.test", password="Pass12345!", role=Roles.MEMBER, branch=branch,
    )
    Member.objects.create(user=student_user, branch=branch, first_name="Ada", last_name="Student")

    client = APIClient()
    client.force_authenticate(leader)
    response = client.get("/api/v1/dashboard/operations/")

    assert response.status_code == 200
    payload = response.data["data"]
    assert payload["metrics"]["groups"] == 1
    assert payload["groups"] == [{"id": str(assigned.id), "name": "Choir Unit", "type": "UNIT", "active_members": 0}]
    assert str(other.id) not in str(payload)


@pytest.mark.django_db
def test_member_cannot_open_staff_operations_workspace():
    organization = Organization.objects.create(name="Chrisland", slug="chrisland-operations-denied")
    branch = Branch.objects.create(name="Chapel", organization=organization, branch_type="CHAPEL")
    user = User.objects.create_user(email="student.denied@example.test", password="Pass12345!", role=Roles.MEMBER, branch=branch)
    client = APIClient()
    client.force_authenticate(user)

    assert client.get("/api/v1/dashboard/operations/").status_code == 403
