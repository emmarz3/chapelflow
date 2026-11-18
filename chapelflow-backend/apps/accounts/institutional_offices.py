"""Approved institutional offices from the Chapel leadership register.

No people or credentials are seeded. A position describes an account's office;
the authorization role and (where applicable) Chapel group remain separate.
"""

from common.constants.roles import Roles


# office_code -> (human-readable office, security role, assigned group name)
# A None group means no mandatory Group assignment. FELLOWSHIP_LEADER is chosen
# from the existing named Campus Fellowship catalog by the Super Admin.
INSTITUTIONAL_OFFICES = {
    "CHAPLAIN": ("Chaplain", Roles.CHAPLAIN, None),
    "STUDENT_CHAPLAIN": ("Student Chaplain", Roles.STUDENT_CHAPLAIN, None),
    "ASSISTANT_STUDENT_CHAPLAIN_VLBC_ANNEX": (
        "Assistant Student Chaplain VLBC Annex Hostel",
        Roles.ASSISTANT_STUDENT_CHAPLAIN, None,
    ),
    "INTERCESSORY": ("Intercessory", Roles.UNIT_HEAD, "Intercessory"),
    "TREASURER": ("Treasurer", Roles.UNIT_HEAD, "Treasurer"),
    "CHAPEL_PROTOCOL": ("Chapel Protocol", Roles.UNIT_HEAD, "Chapel Protocol"),
    "HEAD_OF_MUSIC": ("Head of Music", Roles.UNIT_HEAD, "Music"),
    "ASSISTANT_HEAD_OF_MUSIC": ("Assistant Head of Music", Roles.UNIT_HEAD, "Music"),
    "HEAD_OF_INSTRUMENTALIST": ("Head of Instrumentalist", Roles.UNIT_HEAD, "Instrumentalist"),
    "CHIEF_USHER": ("Chief Usher", Roles.UNIT_HEAD, "Ushering"),
    "ASSISTANT_CHIEF_USHER": ("Assistant Chief Usher", Roles.UNIT_HEAD, "Ushering"),
    "HEAD_OF_SANCTUARY_KEEPERS": ("Head of Sanctuary Keepers", Roles.UNIT_HEAD, "Sanctuary Keepers"),
    "ASSISTANT_HEAD_OF_SANCTUARY_KEEPERS": (
        "Assistant Head of Sanctuary Keepers", Roles.UNIT_HEAD, "Sanctuary Keepers",
    ),
    "MEDIA_ICT": ("Media & ICT", Roles.UNIT_HEAD, "Media & ICT"),
    "SOCIAL_MEDIA": ("Social Media", Roles.UNIT_HEAD, "Social Media"),
    "LIBRARY": ("Library", Roles.UNIT_HEAD, "Library"),
    "DRAMA_TEAM": ("Drama Team", Roles.UNIT_HEAD, "Drama Team"),
    "TECHNICAL_SOUND": ("Technical & Sound", Roles.UNIT_HEAD, "Technical & Sound"),
    "FELLOWSHIP_LEADER": ("Campus Fellowship Leader", Roles.FELLOWSHIP_LEADER, None),
    "MALE_HOSTEL_FELLOWSHIP_COORDINATOR": (
        "Male Hostel Fellowship Coordinator", Roles.HOSTEL_COORDINATOR, None,
    ),
    "FEMALE_HOSTEL_FELLOWSHIP_COORDINATOR_1": (
        "Female Hostel Fellowship Coordinator 1", Roles.HOSTEL_COORDINATOR, None,
    ),
    "FEMALE_HOSTEL_FELLOWSHIP_COORDINATOR_2": (
        "Female Hostel Fellowship Coordinator 2", Roles.HOSTEL_COORDINATOR, None,
    ),
    "ATTENDANCE_USHER": ("Attendance Usher", Roles.ATTENDANCE_USHER, None),
}

# Backward-compatible default for older account-creation clients that choose
# a role and group but do not yet supply an exact office.
DEFAULT_OFFICES_BY_ROLE = {
    Roles.CHAPLAIN: "CHAPLAIN",
    Roles.STUDENT_CHAPLAIN: "STUDENT_CHAPLAIN",
    Roles.UNIT_HEAD: "UNIT_HEAD",
    Roles.FELLOWSHIP_LEADER: "FELLOWSHIP_LEADER",
    Roles.ATTENDANCE_USHER: "ATTENDANCE_USHER",
}
INSTITUTIONAL_OFFICES["UNIT_HEAD"] = ("Unit Leader", Roles.UNIT_HEAD, None)
