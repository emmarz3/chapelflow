import pytest

from apps.operations.models import HomepageContent, HomepageRequest

pytestmark = pytest.mark.django_db

PUBLIC = "/api/v1/site/homepage/"
ADMIN = "/api/v1/operations/homepage/"
REQUESTS = "/api/v1/site/homepage/requests/"


def _content(**overrides):
    content = {
        "siteName": "Chrisland University Chapel",
        "hero": {"titleLead": "Where faith becomes", "titleAccent": "community.", "stats": [{"value": "48", "label": "Programmes"}]},
        "sections": {key: {"enabled": True, "title": key.title()} for key in ("schedule", "events", "sermons", "ministries", "calendar", "gallery")},
        "belonging": {"title": "A richer campus life", "pillars": [{"title": "Worship", "detail": "Together"}]},
        "closing": {"title": "Stay connected"},
        "countdown": {"enabled": True, "serviceId": "svc-1"},
        "verse": {"enabled": True, "verses": [{"id": "v-1", "text": "Text", "reference": "Psalm 23:1"}]},
        "announcements": [{"id": "ann-1", "text": "Service moved", "linkLabel": "See", "linkHref": "#schedule", "active": True}],
        "services": [{"id": "svc-1", "type": "midweek", "title": "Midweek", "venue": "Hall", "time": "17:00", "duration": 90, "rule": "weekly", "weekday": 3}],
        "events": [{"id": "evt-1", "category": "Retreat", "title": "Retreat", "startDate": "2026-10-09", "startTime": "16:00", "time": "Fri 4 PM", "venue": "Grounds", "capacity": 2, "taken": 1}],
        "sermons": [{"id": "srm-1", "title": "Faith", "date": "2026-09-13", "videoUrl": "https://example.com/watch"}],
        "units": [{"id": "unit-1", "name": "Choir", "icon": "music"}],
        "gallery": [{"id": "gal-1", "title": "Baptism", "imageUrl": "/images/baptism.jpg"}],
        "contact": {"address": "Abeokuta", "email": "chapel@example.edu"},
    }
    content.update(overrides)
    return content


def _save(client, user, content, version=0):
    client.force_authenticate(user)
    return client.put(ADMIN, {"content": content, "version": version}, format="json")


def test_public_endpoint_is_anonymous_and_empty_until_first_save(api_client):
    res = api_client.get(PUBLIC)
    assert res.status_code == 200
    assert res.data["data"]["content"] is None
    assert res.data["data"]["version"] == 0


def test_only_super_admin_can_edit(api_client, chapel_admin_a, member_in_branch_a):
    assert api_client.put(ADMIN, {"content": _content(), "version": 0}, format="json").status_code in (401, 403)
    assert _save(api_client, chapel_admin_a, _content()).status_code == 403
    api_client.force_authenticate(member_in_branch_a.user)
    assert api_client.get(ADMIN).status_code == 403
    assert api_client.delete(ADMIN).status_code == 403


def test_super_admin_save_is_public_and_versioned(api_client, super_admin):
    res = _save(api_client, super_admin, _content())
    assert res.status_code == 200, res.data
    assert res.data["data"]["version"] == 1
    api_client.force_authenticate(user=None)
    public = api_client.get(PUBLIC).data["data"]
    assert public["content"]["hero"]["titleLead"] == "Where faith becomes"
    assert public["content"]["units"][0]["name"] == "Choir"


def test_stale_version_is_rejected(api_client, super_admin):
    assert _save(api_client, super_admin, _content()).status_code == 200
    stale = _save(api_client, super_admin, _content(siteName="Other"), version=0)
    assert stale.status_code == 409
    assert HomepageContent.objects.get().content["siteName"] == "Chrisland University Chapel"


@pytest.mark.parametrize(
    "path,mutate",
    [
        ("announcements[0].linkHref", lambda c: c["announcements"][0].update(linkHref="javascript:alert(1)")),
        ("sermons[0].videoUrl", lambda c: c["sermons"][0].update(videoUrl="data:text/html,<script>")),
        ("gallery[0].imageUrl", lambda c: c["gallery"][0].update(imageUrl="//evil.example/x.png")),
        ("services[0].time", lambda c: c["services"][0].update(time="25:99")),
        ("events[0].startDate", lambda c: c["events"][0].update(startDate="2026-13-40")),
        ("units[0].icon", lambda c: c["units"][0].update(icon="skull")),
        ("services[0].rule", lambda c: c["services"][0].update(rule="hourly")),
        ("contact.email", lambda c: c["contact"].update(email="not-an-email")),
        ("siteName", lambda c: c.update(siteName="")),
        ("countdown.serviceId", lambda c: c["countdown"].update(serviceId="missing")),
    ],
)
def test_invalid_content_is_rejected_with_field_paths(api_client, super_admin, path, mutate):
    content = _content()
    mutate(content)
    res = _save(api_client, super_admin, content)
    assert res.status_code == 400
    assert path in res.data["errors"]
    assert HomepageContent.objects.count() == 0 or HomepageContent.objects.get().version == 0


def test_duplicate_ids_and_list_limits(api_client, super_admin):
    content = _content(units=[{"id": "same", "name": "A"}, {"id": "same", "name": "B"}])
    res = _save(api_client, super_admin, content)
    assert res.status_code == 400 and "units[1].id" in res.data["errors"]
    too_many = _content(announcements=[{"id": f"a-{i}", "text": "x"} for i in range(11)])
    assert "announcements" in _save(api_client, super_admin, too_many).data["errors"]


def test_unknown_keys_are_not_persisted(api_client, super_admin):
    content = _content()
    content["evil"] = "<script>"
    content["hero"]["extra"] = "x"
    assert _save(api_client, super_admin, content).status_code == 200
    stored = HomepageContent.objects.get().content
    assert "evil" not in stored and "extra" not in stored["hero"]


def test_reset_restores_defaults_for_client(api_client, super_admin):
    assert _save(api_client, super_admin, _content()).status_code == 200
    res = api_client.delete(ADMIN)
    assert res.status_code == 200
    assert api_client.get(PUBLIC).data["data"]["content"] is None


def _rsvp(client, **overrides):
    payload = {"kind": "event", "itemId": "evt-1", "itemTitle": "Retreat", "name": "Ada Obi", "email": "ada@example.com", "matricNo": "22/1", "consent": True}
    payload.update(overrides)
    return client.post(REQUESTS, payload, format="json")


def test_public_signup_counts_toward_places_and_is_idempotent(api_client, super_admin):
    _save(api_client, super_admin, _content())  # capacity 2, one already taken offline
    api_client.force_authenticate(user=None)
    assert _rsvp(api_client).status_code == 201
    assert _rsvp(api_client, email="ADA@example.com").status_code == 201  # same person again
    assert HomepageRequest.objects.count() == 1
    assert api_client.get(PUBLIC).data["data"]["counts"] == {"evt-1": 1}
    full = _rsvp(api_client, email="grace@example.com", name="Grace Ade")
    assert full.status_code == 409  # 1 offline + 1 online = capacity 2


def test_signup_requires_consent_valid_email_and_known_item(api_client, super_admin):
    _save(api_client, super_admin, _content())
    api_client.force_authenticate(user=None)
    bad = _rsvp(api_client, consent=False, email="nope", name="A")
    assert bad.status_code == 400 and {"consent", "email", "name"} <= set(bad.data["errors"])
    assert _rsvp(api_client, itemId="does-not-exist").status_code == 404
    assert _rsvp(api_client, kind="unit", itemId="evt-1").status_code == 404


def test_hidden_items_reject_signups(api_client, super_admin):
    content = _content()
    content["units"][0]["active"] = False
    _save(api_client, super_admin, content)
    api_client.force_authenticate(user=None)
    assert _rsvp(api_client, kind="unit", itemId="unit-1").status_code == 404


def test_unit_join_and_honeypot(api_client, super_admin):
    _save(api_client, super_admin, _content())
    api_client.force_authenticate(user=None)
    assert _rsvp(api_client, kind="unit", itemId="unit-1", itemTitle="Choir").status_code == 201
    assert _rsvp(api_client, kind="unit", itemId="unit-1", email="bot@example.com", website="http://spam").status_code == 201
    assert HomepageRequest.objects.filter(email="bot@example.com").count() == 0


def test_super_admin_manages_signups(api_client, super_admin, chapel_admin_a):
    _save(api_client, super_admin, _content())
    api_client.force_authenticate(user=None)
    _rsvp(api_client)
    api_client.force_authenticate(chapel_admin_a)
    assert api_client.get(ADMIN + "requests/").status_code == 403
    api_client.force_authenticate(super_admin)
    listing = api_client.get(ADMIN + "requests/?kind=event&search=ada")
    assert listing.status_code == 200 and listing.data["data"]["total"] == 1
    row = listing.data["data"]["results"][0]
    assert row["itemTitle"] == "Retreat"
    patched = api_client.patch(f"{ADMIN}requests/{row['id']}/", {"status": "CONTACTED"}, format="json")
    assert patched.status_code == 200 and patched.data["data"]["status"] == "CONTACTED"
    assert api_client.patch(f"{ADMIN}requests/{row['id']}/", {"status": "BOGUS"}, format="json").status_code == 400
    assert api_client.delete(f"{ADMIN}requests/{row['id']}/").status_code == 200
    assert HomepageRequest.objects.count() == 0
