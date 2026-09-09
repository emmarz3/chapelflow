# University vs. Chapel structure (spec section 2 & 7)

Two independent hierarchies, both hanging off `apps.members.Member`:

```
ACADEMIC (apps.university)          CHAPEL (apps.organizations + apps.ministries)
University                          Organization
  └── College                         └── Branch (a Chapel/Campus)
        └── Department                      ├── Fellowship  (Group, group_type=FELLOWSHIP)
                                             ├── Unit        (Group, group_type=UNIT)
                                             └── Ministry    (Group, group_type=MINISTRY)
```

A `Member` has:
- at most one `college` and one `department` (FKs, nullable)
- at most one `fellowship` (FK to `ministries.Group`, `group_type=FELLOWSHIP`)
- many Units and many Ministries/Groups — via `groups.GroupMembership`
  (already supported: it's a through-table, not a single FK)
- a `community` classification: `STUDENT` or `STAFF` — **not** a role,
  used for segmentation/reporting/communication targeting only

`apps.ministries.Group.GroupType.DEPARTMENT` and `.COMMUNITY` are legacy
values kept only so existing rows don't break validation. Nothing should
create new Groups with those types — `DEPARTMENT` in the old model was
exactly the anti-pattern spec section 7 calls out ("do NOT use Chapel
Groups as a replacement for College/Department").

## Multiple leaders per Fellowship/Unit/Ministry

**Resolved in the Phase 0 follow-up session; `Group.leader` formally
deprecated in this session.** `Group.leader` (single FK) is kept ONLY for
backward compatibility with existing data/reports — it is now marked
deprecated in its own `help_text` and in `Group`'s class docstring, and
the DB column is intentionally **not** dropped yet (see removal plan
below). The source of truth for leadership — and for scoping — is
`groups.GroupMembership` with `role=LEADER`, via
`common/permissions/scoping.py::led_group_ids()` for scoping decisions and
`apps/groups/serializers.py::active_leader_memberships()` for building a
leadership listing to display. `GroupSerializer` now exposes both:
`leader` (deprecated, writable, for old integrations) and `leaders`
(the real, multi-leader-capable, read-only listing) — new code should
read/write `leaders`/`GroupMembership`, never `leader`.

A Group can have any number of active leaders; each is scoped to only
that Group (and only within the Group *type* their role corresponds to —
a Unit Head's leadership of an unrelated Fellowship, for example, never
grants Fellowship-level access). `BranchScopedQuerysetMixin` subclasses
opt in to leader-scoping by setting `group_field_lookup` (`"id"` if the
model IS `Group`, or the FK field name if it points at one) — see
`apps/ministries/views.py::GroupViewSet` and
`apps/groups/views.py::GroupMembershipViewSet` for the two current uses.

### `Group.leader` removal plan

Not removed in this session — removing a column is a breaking, one-way
change and should happen only once nothing reads it. Before dropping it:
1. Confirm no remaining call site reads `Group.leader` for anything other
   than display/back-compat (grep for `.leader` outside `led_groups`
   should return only the serializer's deprecated pass-through field).
2. Backfill: for any `Group` where `leader` is set but has no
   corresponding active `GroupMembership(role=LEADER)` row, create one —
   otherwise dropping the column silently loses that leadership record.
3. Only then: a Django migration to remove the field, plus removing it
   from `GroupSerializer.Meta.fields`.
