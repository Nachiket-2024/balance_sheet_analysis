# Roles Are Metadata, Not the Enforcement Mechanism

"Analyst"/"CEO"/"group executive" are personas for humans to reason about
(and for seeding convenience), not literal RBAC rows. The `User.role`
column (from mystic_auth) is display metadata only, exactly as it is for
mystic_auth's own users; every actual allow/deny decision here is a PBAC
policy evaluation against the specific resource being requested, per
[`../../mystic_auth/security/decisions.md`](../../mystic_auth/security/decisions.md#role-is-never-used-to-decide-access).
A single "CEO" policy *definition* (e.g. "read, scoped to one company_id") is
reused for every CEO: only the `company_id` value in each user's own
assignment differs.
