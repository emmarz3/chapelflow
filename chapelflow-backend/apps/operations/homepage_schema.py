"""Validation and sanitisation for the Super-Admin-managed homepage document.

The document is a plain JSON object whose shape mirrors
``src/lib/homepage-content.ts`` on the client. Nothing is trusted: every
field is type-checked, length-limited and copied into a fresh dictionary, so
unknown keys can never be persisted and unsafe URL schemes (``javascript:``,
``data:`` ...) can never reach a public page.
"""
import re
from datetime import date

from django.core.validators import validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

SERVICE_TYPES = ("sunday", "midweek", "vigil")
SERVICE_RULES = ("weekly", "lastfri", "date")
EVENT_CTAS = ("Register", "RSVP")
UNIT_ICONS = (
    "music", "door", "camera", "flame", "smile", "shield", "heart", "book",
    "users", "mic", "megaphone", "star",
)
SECTION_KEYS = ("schedule", "events", "sermons", "ministries", "calendar", "gallery")

LIMITS = {
    "announcements": 10,
    "services": 30,
    "events": 40,
    "sermons": 40,
    "units": 30,
    "gallery": 40,
    "verses": 400,
    "stats": 4,
    "pillars": 6,
}


class HomepageValidationError(Exception):
    def __init__(self, errors):
        super().__init__("Homepage content is invalid.")
        self.errors = errors


class _Ctx:
    def __init__(self):
        self.errors = {}

    def fail(self, path, message):
        self.errors.setdefault(path, []).append(message)

    # -- primitives -----------------------------------------------------
    def text(self, value, path, max_len, *, required=False, default=""):
        if value is None or value == "":
            if required:
                self.fail(path, "This field is required.")
            return default
        if not isinstance(value, str):
            self.fail(path, "Must be text.")
            return default
        value = CONTROL_RE.sub("", value).strip()
        if required and not value:
            self.fail(path, "This field is required.")
        if len(value) > max_len:
            self.fail(path, f"Must be {max_len} characters or fewer.")
            return value[:max_len]
        return value

    def boolean(self, value, path, default=True):
        if value is None:
            return default
        if not isinstance(value, bool):
            self.fail(path, "Must be true or false.")
            return default
        return value

    def integer(self, value, path, *, minimum=0, maximum=100000, default=None):
        if value is None or value == "":
            return default
        if isinstance(value, bool) or not isinstance(value, int):
            self.fail(path, "Must be a whole number.")
            return default
        if value < minimum or value > maximum:
            self.fail(path, f"Must be between {minimum} and {maximum}.")
            return default
        return value

    def choice(self, value, path, allowed, default):
        if value is None or value == "":
            return default
        if value not in allowed:
            self.fail(path, f"Must be one of: {', '.join(allowed)}.")
            return default
        return value

    def url(self, value, path, *, allow_anchor=False, max_len=500):
        value = self.text(value, path, max_len)
        if not value:
            return ""
        lowered = value.lower()
        if lowered.startswith(("https://", "http://")):
            if " " in value:
                self.fail(path, "Web addresses cannot contain spaces.")
                return ""
            return value
        if value.startswith("/") and not value.startswith("//") and " " not in value:
            return value
        if allow_anchor and re.match(r"^#[A-Za-z0-9_-]+$", value):
            return value
        self.fail(
            path,
            "Use a full https:// address, a site path starting with /"
            + (", or a #section anchor." if allow_anchor else "."),
        )
        return ""

    def clock(self, value, path, *, required=True):
        value = self.text(value, path, 5, required=required)
        if value and not TIME_RE.match(value):
            self.fail(path, "Use 24-hour time such as 09:00 or 17:30.")
            return ""
        return value

    def iso_date(self, value, path, *, required=False):
        value = self.text(value, path, 10, required=required)
        if not value:
            return ""
        try:
            date.fromisoformat(value)
        except ValueError:
            self.fail(path, "Use a valid date in YYYY-MM-DD format.")
            return ""
        return value

    def item_id(self, value, path):
        value = self.text(value, path, 64, required=True)
        if value and not ID_RE.match(value):
            self.fail(path, "IDs may use lowercase letters, numbers, hyphens and underscores.")
        return value

    def items(self, value, path, key, builder):
        if value is None:
            return []
        if not isinstance(value, list):
            self.fail(path, "Must be a list.")
            return []
        if len(value) > LIMITS[key]:
            self.fail(path, f"No more than {LIMITS[key]} entries are allowed.")
            value = value[: LIMITS[key]]
        seen, out = set(), []
        for index, raw in enumerate(value):
            item_path = f"{path}[{index}]"
            if not isinstance(raw, dict):
                self.fail(item_path, "Must be an object.")
                continue
            cleaned = builder(raw, item_path)
            if "id" in cleaned:
                if cleaned["id"] in seen:
                    self.fail(f"{item_path}.id", "Duplicate ID.")
                seen.add(cleaned["id"])
            out.append(cleaned)
        return out


def _obj(ctx, value, path):
    if value is None:
        return {}
    if not isinstance(value, dict):
        ctx.fail(path, "Must be an object.")
        return {}
    return value


def _hero(ctx, raw, path):
    raw = _obj(ctx, raw, path)

    def stat(item, p):
        return {
            "value": ctx.text(item.get("value"), f"{p}.value", 20, required=True),
            "label": ctx.text(item.get("label"), f"{p}.label", 40, required=True),
        }

    return {
        "eyebrow": ctx.text(raw.get("eyebrow"), f"{path}.eyebrow", 80),
        "titleLead": ctx.text(raw.get("titleLead"), f"{path}.titleLead", 120, required=True),
        "titleAccent": ctx.text(raw.get("titleAccent"), f"{path}.titleAccent", 60),
        "lede": ctx.text(raw.get("lede"), f"{path}.lede", 400),
        "primaryLabel": ctx.text(raw.get("primaryLabel"), f"{path}.primaryLabel", 60),
        "primaryHref": ctx.url(raw.get("primaryHref"), f"{path}.primaryHref", allow_anchor=True),
        "secondaryLabel": ctx.text(raw.get("secondaryLabel"), f"{path}.secondaryLabel", 60),
        "secondaryHref": ctx.url(raw.get("secondaryHref"), f"{path}.secondaryHref", allow_anchor=True),
        "imageUrl": ctx.url(raw.get("imageUrl"), f"{path}.imageUrl"),
        "imageCaption": ctx.text(raw.get("imageCaption"), f"{path}.imageCaption", 120),
        "stats": ctx.items(raw.get("stats"), f"{path}.stats", "stats", stat),
    }


def _sections(ctx, raw, path):
    raw = _obj(ctx, raw, path)
    out = {}
    for key in SECTION_KEYS:
        section = _obj(ctx, raw.get(key), f"{path}.{key}")
        p = f"{path}.{key}"
        out[key] = {
            "enabled": ctx.boolean(section.get("enabled"), f"{p}.enabled"),
            "eyebrow": ctx.text(section.get("eyebrow"), f"{p}.eyebrow", 60),
            "title": ctx.text(section.get("title"), f"{p}.title", 100, required=True),
            "description": ctx.text(section.get("description"), f"{p}.description", 300),
        }
    return out


def _belonging(ctx, raw, path):
    raw = _obj(ctx, raw, path)

    def pillar(item, p):
        return {
            "title": ctx.text(item.get("title"), f"{p}.title", 60, required=True),
            "detail": ctx.text(item.get("detail"), f"{p}.detail", 120),
        }

    return {
        "eyebrow": ctx.text(raw.get("eyebrow"), f"{path}.eyebrow", 80),
        "title": ctx.text(raw.get("title"), f"{path}.title", 140, required=True),
        "body": ctx.text(raw.get("body"), f"{path}.body", 500),
        "quote": ctx.text(raw.get("quote"), f"{path}.quote", 200),
        "pillars": ctx.items(raw.get("pillars"), f"{path}.pillars", "pillars", pillar),
    }


def _closing(ctx, raw, path):
    raw = _obj(ctx, raw, path)
    return {
        "eyebrow": ctx.text(raw.get("eyebrow"), f"{path}.eyebrow", 80),
        "title": ctx.text(raw.get("title"), f"{path}.title", 160, required=True),
        "body": ctx.text(raw.get("body"), f"{path}.body", 400),
        "ctaLabel": ctx.text(raw.get("ctaLabel"), f"{path}.ctaLabel", 60),
    }


def _announcement(ctx, raw, p):
    return {
        "id": ctx.item_id(raw.get("id"), f"{p}.id"),
        "text": ctx.text(raw.get("text"), f"{p}.text", 220, required=True),
        "linkLabel": ctx.text(raw.get("linkLabel"), f"{p}.linkLabel", 40),
        "linkHref": ctx.url(raw.get("linkHref"), f"{p}.linkHref", allow_anchor=True),
        "active": ctx.boolean(raw.get("active"), f"{p}.active"),
    }


def _service(ctx, raw, p):
    rule = ctx.choice(raw.get("rule"), f"{p}.rule", SERVICE_RULES, "weekly")
    out = {
        "id": ctx.item_id(raw.get("id"), f"{p}.id"),
        "type": ctx.choice(raw.get("type"), f"{p}.type", SERVICE_TYPES, "sunday"),
        "title": ctx.text(raw.get("title"), f"{p}.title", 140, required=True),
        "venue": ctx.text(raw.get("venue"), f"{p}.venue", 140, required=True),
        "minister": ctx.text(raw.get("minister"), f"{p}.minister", 140),
        "time": ctx.clock(raw.get("time"), f"{p}.time"),
        "duration": ctx.integer(raw.get("duration"), f"{p}.duration", minimum=15, maximum=1440, default=90),
        "rule": rule,
        "weekday": ctx.integer(raw.get("weekday"), f"{p}.weekday", minimum=0, maximum=6, default=0),
        "date": ctx.iso_date(raw.get("date"), f"{p}.date", required=(rule == "date")),
        "active": ctx.boolean(raw.get("active"), f"{p}.active"),
    }
    return out


def _event(ctx, raw, p):
    repeat = ctx.choice(raw.get("repeat"), f"{p}.repeat", ("none", "weekly"), "none")
    start = ctx.iso_date(raw.get("startDate"), f"{p}.startDate", required=(repeat == "none"))
    end = ctx.iso_date(raw.get("endDate"), f"{p}.endDate")
    if start and end and end < start:
        ctx.fail(f"{p}.endDate", "The end date cannot be before the start date.")
    return {
        "id": ctx.item_id(raw.get("id"), f"{p}.id"),
        "category": ctx.text(raw.get("category"), f"{p}.category", 40, required=True),
        "title": ctx.text(raw.get("title"), f"{p}.title", 140, required=True),
        "repeat": repeat,
        "weekday": ctx.integer(raw.get("weekday"), f"{p}.weekday", minimum=0, maximum=6, default=0),
        "startDate": start,
        "endDate": end,
        "startTime": ctx.clock(raw.get("startTime"), f"{p}.startTime"),
        "time": ctx.text(raw.get("time"), f"{p}.time", 80, required=True),
        "venue": ctx.text(raw.get("venue"), f"{p}.venue", 140, required=True),
        "host": ctx.text(raw.get("host"), f"{p}.host", 140),
        "cta": ctx.choice(raw.get("cta"), f"{p}.cta", EVENT_CTAS, "Register"),
        "capacity": ctx.integer(raw.get("capacity"), f"{p}.capacity", minimum=1, default=None),
        "taken": ctx.integer(raw.get("taken"), f"{p}.taken", default=0),
        "active": ctx.boolean(raw.get("active"), f"{p}.active"),
    }


def _sermon(ctx, raw, p):
    return {
        "id": ctx.item_id(raw.get("id"), f"{p}.id"),
        "series": ctx.text(raw.get("series"), f"{p}.series", 80),
        "title": ctx.text(raw.get("title"), f"{p}.title", 160, required=True),
        "speaker": ctx.text(raw.get("speaker"), f"{p}.speaker", 140),
        "date": ctx.iso_date(raw.get("date"), f"{p}.date", required=True),
        "duration": ctx.text(raw.get("duration"), f"{p}.duration", 12),
        "videoUrl": ctx.url(raw.get("videoUrl"), f"{p}.videoUrl"),
        "audioUrl": ctx.url(raw.get("audioUrl"), f"{p}.audioUrl"),
        "downloadUrl": ctx.url(raw.get("downloadUrl"), f"{p}.downloadUrl"),
        "imageUrl": ctx.url(raw.get("imageUrl"), f"{p}.imageUrl"),
        "active": ctx.boolean(raw.get("active"), f"{p}.active"),
    }


def _unit(ctx, raw, p):
    return {
        "id": ctx.item_id(raw.get("id"), f"{p}.id"),
        "name": ctx.text(raw.get("name"), f"{p}.name", 80, required=True),
        "icon": ctx.choice(raw.get("icon"), f"{p}.icon", UNIT_ICONS, "users"),
        "description": ctx.text(raw.get("description"), f"{p}.description", 300),
        "meeting": ctx.text(raw.get("meeting"), f"{p}.meeting", 120),
        "active": ctx.boolean(raw.get("active"), f"{p}.active"),
    }


def _gallery(ctx, raw, p):
    return {
        "id": ctx.item_id(raw.get("id"), f"{p}.id"),
        "title": ctx.text(raw.get("title"), f"{p}.title", 120, required=True),
        "subtitle": ctx.text(raw.get("subtitle"), f"{p}.subtitle", 80),
        "imageUrl": ctx.url(raw.get("imageUrl"), f"{p}.imageUrl"),
        "active": ctx.boolean(raw.get("active"), f"{p}.active"),
    }


def _verse(ctx, raw, p):
    return {
        "id": ctx.item_id(raw.get("id"), f"{p}.id"),
        "text": ctx.text(raw.get("text"), f"{p}.text", 600, required=True),
        "reference": ctx.text(raw.get("reference"), f"{p}.reference", 60, required=True),
        "translation": ctx.text(raw.get("translation"), f"{p}.translation", 20),
        "note": ctx.text(raw.get("note"), f"{p}.note", 400),
    }


def sanitize_homepage(raw):
    """Return a clean copy of ``raw`` or raise ``HomepageValidationError``."""
    ctx = _Ctx()
    if not isinstance(raw, dict):
        raise HomepageValidationError({"content": ["Homepage content must be an object."]})

    countdown = _obj(ctx, raw.get("countdown"), "countdown")
    verse = _obj(ctx, raw.get("verse"), "verse")
    contact = _obj(ctx, raw.get("contact"), "contact")

    services = ctx.items(raw.get("services"), "services", "services", lambda r, p: _service(ctx, r, p))
    service_ids = {s["id"] for s in services}
    countdown_service = ctx.text(countdown.get("serviceId"), "countdown.serviceId", 64)
    if countdown_service and countdown_service not in service_ids:
        ctx.fail("countdown.serviceId", "Choose one of your services.")
        countdown_service = ""

    cleaned = {
        "siteName": ctx.text(raw.get("siteName"), "siteName", 120, required=True),
        "hero": _hero(ctx, raw.get("hero"), "hero"),
        "sections": _sections(ctx, raw.get("sections"), "sections"),
        "belonging": _belonging(ctx, raw.get("belonging"), "belonging"),
        "closing": _closing(ctx, raw.get("closing"), "closing"),
        "countdown": {
            "enabled": ctx.boolean(countdown.get("enabled"), "countdown.enabled"),
            "serviceId": countdown_service,
        },
        "verse": {
            "enabled": ctx.boolean(verse.get("enabled"), "verse.enabled"),
            "verses": ctx.items(verse.get("verses"), "verse.verses", "verses", lambda r, p: _verse(ctx, r, p)),
        },
        "announcements": ctx.items(
            raw.get("announcements"), "announcements", "announcements", lambda r, p: _announcement(ctx, r, p)
        ),
        "services": services,
        "events": ctx.items(raw.get("events"), "events", "events", lambda r, p: _event(ctx, r, p)),
        "sermons": ctx.items(raw.get("sermons"), "sermons", "sermons", lambda r, p: _sermon(ctx, r, p)),
        "units": ctx.items(raw.get("units"), "units", "units", lambda r, p: _unit(ctx, r, p)),
        "gallery": ctx.items(raw.get("gallery"), "gallery", "gallery", lambda r, p: _gallery(ctx, r, p)),
        "contact": {
            "address": ctx.text(contact.get("address"), "contact.address", 240),
            "email": _email(ctx, contact.get("email"), "contact.email"),
            "phone": ctx.text(contact.get("phone"), "contact.phone", 40),
            "facebook": ctx.url(contact.get("facebook"), "contact.facebook"),
            "x": ctx.url(contact.get("x"), "contact.x"),
            "instagram": ctx.url(contact.get("instagram"), "contact.instagram"),
            "youtube": ctx.url(contact.get("youtube"), "contact.youtube"),
        },
    }
    if ctx.errors:
        raise HomepageValidationError(ctx.errors)
    return cleaned


def _email(ctx, value, path):
    value = ctx.text(value, path, 254)
    if not value:
        return ""
    try:
        validate_email(value)
    except DjangoValidationError:
        ctx.fail(path, "Enter a valid email address.")
        return ""
    return value
