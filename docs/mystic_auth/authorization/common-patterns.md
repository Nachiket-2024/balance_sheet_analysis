# Common Authorization Patterns

Unlike [Policy JSON Examples](policy-examples.md) (what a condition type's JSON looks like) or [Condition Schema Reference](condition-schema-reference.md) (the exact fields each condition type accepts), this page is about **modeling choices on your own resource tables** to get a common real-world access shape out of PBAC's existing, deliberately small set of condition types. Nothing here requires a new condition type or any change to `mystic_auth/`: every pattern below is achievable with what already ships.

## Scoping access to a hierarchy (org chart, company group, folder tree)

**The need:** "this user can see every project under division X": projects/teams/companies form a tree, not a flat list.

**Why it doesn't fit directly:** [`resource_attributes`](condition-schema-reference.md#resource_attributes) only ever does flat equality on a field of the resource: there's no built-in "any descendant of X" traversal, and there isn't meant to be; PBAC's condition set is intentionally small and generic rather than growing a bespoke operator for every domain shape.

**The pattern:** the fix is a modeling choice on *your own* resource table, one level below PBAC entirely. Alongside whatever self-referential `parent_id` column your table already has for the real tree structure, add a second, denormalized column that's always the top-most ancestor's id (equal to its own id for a root row), maintained by a small helper on insert/update. A policy then scopes on *that* column with plain flat equality: no traversal needed at authorization time, because the traversal already happened once, at write time, instead of on every check.

A user scoped to a whole division:

```json
{
  "name": "division_lead_engineering",
  "description": "Full visibility into every project under the Engineering division, at any depth",
  "actions": ["projects:read"],
  "resource_type": "projects",
  "conditions": {
    "resource_attributes": {"division_root_id": 42}
  }
}
```

A user scoped to one specific project instead (not a whole division) uses the same condition key, just against the resource's own id rather than its denormalized root:

```json
{
  "name": "project_lead_atlas",
  "description": "Full visibility into the Atlas project specifically",
  "actions": ["projects:read"],
  "resource_type": "projects",
  "conditions": {
    "resource_attributes": {"project_id": 7}
  }
}
```

Both policies use the exact same condition type and the exact same route-side code (`require_authorization("projects:read", "projects")` with the resource passed in for evaluation): only the scoping *data* differs, which is the whole point of PBAC being data-driven rather than code-driven.
