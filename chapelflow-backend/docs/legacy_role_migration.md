# Legacy role migration strategy (Phase 0, spec section 5 & 22)

## Status: documented, NOT auto-applied for ambiguous roles

Per the Phase 0 instruction ("where a legacy role mapping is ambiguous, do
NOT invent a mapping — document it and preserve the old data safely until
explicitly resolved"), this migration is split into two tiers.

## Tier 1 — unambiguous, safe to run now

| Legacy role       | New role                | Confidence | Rationale |
|--------------------|--------------------------|------------|-----------|
| `PASTOR`           | `CHAPLAIN`               | High       | "Highest Chapel authority" in both models; only one senior clergy role existed before. |
| `UNIT_LEADER`      | `UNIT_HEAD`              | High       | Same scope (manages one Unit), name change only. |
| `VOLUNTEER`        | `MEMBER` + a `Volunteer` tag/flag (see `apps.volunteers`) | High | Spec has no standalone Volunteer *role* — volunteering is something a Member does, tracked via `apps.volunteers.VolunteerProfile`, not a login role. |

These three are implemented in `scripts/migrate_legacy_roles.py` under
`--apply-tier-1`.

## Tier 2 — ambiguous, intentionally NOT auto-migrated

| Legacy role         | Candidate new role(s)                              | Why it's ambiguous |
|----------------------|-----------------------------------------------------|---------------------|
| `FINANCE_OFFICER`    | No direct equivalent in the University Edition role list | The spec's role list (section 1) does not name a Finance role at all — finance authorization currently runs on `FINANCE_ACCESS_ROLES`, not a dedicated login role. Converting existing Finance Officers to `CHAPEL_ADMIN` would silently grant them the *entire* Chapel Admin permission surface, not just finance — an unintended privilege escalation. This needs an explicit product decision: either (a) add `FINANCE_OFFICER` back into the University Edition role list, or (b) convert these accounts to `CHAPEL_ADMIN` and rely on `RolePermission` to scope them down to finance-only permission codes. |
| `COMMUNITY_LEADER`   | `FELLOWSHIP_LEADER`, `MINISTRY_GROUP_LEADER`, or `CHAPEL_ADMIN` | "Community" was a broader/vaguer legacy grouping than Fellowship/Unit/Ministry. Which one a given Community Leader maps to depends on what `Group`(s) they actually led — needs to be checked per-user against their existing `GroupMembership` rows with `role=LEADER`. |
| `MINISTRY_LEADER`    | `MINISTRY_GROUP_LEADER` | Looks unambiguous by name, but the legacy `Group` model didn't distinguish Ministry/Group from Fellowship/Unit the way spec section 7 now requires — must be resolved together with the `Group.group_type` backfill (see `docs/university_structure.md`), not in isolation. |
| `DEPARTMENT_LEADER`  | Not a login role at all in University Edition | Spec section 2 makes Department part of the *academic* hierarchy (University → College → Department), which has no "leader" role — Chapel-side leadership only exists at Fellowship/Unit/Ministry level. Existing `DEPARTMENT_LEADER` accounts most likely correspond to a Unit or Ministry that happened to be organized around an academic department; needs manual review. |

**Do not bulk-assign Tier 2 roles.** Run
`scripts/migrate_legacy_roles.py --report-tier-2` to get a CSV of every
affected user with their current role, branch, and any `GroupMembership`
leadership rows, for a human (Chaplain/Super Admin) to resolve one by one.

## How the data stays safe in the meantime

- `Roles.LEGACY_CHOICES` remains valid on the `User.role` field, so nothing
  breaks for users who haven't been migrated yet.
- `Roles.CURRENT_CHOICES` is what new registration/role-assignment flows
  must use — legacy values are never assignable to new users
  (enforced in `apps/accounts/serializers.py::validate_role`, added in this
  phase).
- `RolePermission` rows for legacy roles are left untouched; permissions
  are not silently revoked from anyone until they're migrated.
