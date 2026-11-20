import pytest


@pytest.mark.django_db
def test_member_pdf_exports_all_pages_and_respects_filters(api_client, super_admin, branch_a, monkeypatch):
    from reportlab.platypus import KeepTogether, SimpleDocTemplate
    from apps.members.models import Member

    for index in range(30):
        Member.objects.create(branch=branch_a, first_name="Export", last_name=f"Person{index:02d}")
    Member.objects.create(branch=branch_a, first_name="Other", last_name="Person")
    captured = []
    original_build = SimpleDocTemplate.build

    def capture(self, flowables, *args, **kwargs):
        captured.append(sum(isinstance(item, KeepTogether) for item in flowables))
        return original_build(self, flowables, *args, **kwargs)

    monkeypatch.setattr(SimpleDocTemplate, "build", capture)
    api_client.force_authenticate(super_admin)
    response = api_client.get("/api/v1/members/export-pdf/?search=Export&page=1&page_size=1")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Cache-Control"] == "private, no-store"
    assert response.content.startswith(b"%PDF-")
    assert captured == [30]


@pytest.mark.django_db
def test_member_pdf_stays_within_authorized_branch(api_client, chapel_admin_a, branch_a, branch_b, seed_member_permissions, monkeypatch):
    from reportlab.platypus import KeepTogether, SimpleDocTemplate
    from apps.members.models import Member

    Member.objects.create(branch=branch_a, first_name="Local", last_name="Student")
    Member.objects.create(branch=branch_b, first_name="Other", last_name="Student")
    captured = []
    original_build = SimpleDocTemplate.build

    def capture(self, flowables, *args, **kwargs):
        captured.append(sum(isinstance(item, KeepTogether) for item in flowables))
        return original_build(self, flowables, *args, **kwargs)

    monkeypatch.setattr(SimpleDocTemplate, "build", capture)
    api_client.force_authenticate(chapel_admin_a)
    response = api_client.get("/api/v1/members/export-pdf/")
    assert response.status_code == 200
    assert captured == [1]
