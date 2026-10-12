# Glossary: Authorization (PBAC)
---

Policies, permissions, and access-decision terms. See [Glossary](README.md) for the full index.

---

## PBAC

Short for Policy-Based Access Control: this app's authorization model. Every access decision comes from evaluating a caller's assigned policies (an action list, a resource type, and optional conditions) against the specific request, rather than checking a role directly. See [Authorization Architecture Overview](../authorization/architecture/README.md).

---

## role-based access control

Short for Role-Based Access Control: the more familiar "give this role these permissions" model. This app doesn't use role-based access control as a separate system; instead you can shape PBAC's policies to behave like roles when you don't need per-request conditions. See [Unconditioned Policy Quickstart](../authorization/unconditioned-policy-quickstart.md).

---

## policy

A named record that grants a set of actions on a resource type, optionally narrowed by conditions (e.g. "only during business hours" or "only your own records"). Policies are assigned to users and are the only thing PBAC checks when deciding "can this caller do this." See [Policy JSON Examples](../authorization/policy-examples.md).

---

## condition handler

The piece of code that knows how to evaluate one specific condition type inside a policy (for example, "is the current time within this window" or "does this resource belong to the caller"). The policy evaluation engine itself doesn't know what any condition means; it just delegates each one to its registered handler. See [Authorization Architecture: Condition Evaluation Service](../authorization/architecture/component-responsibilities.md#condition-evaluation-service) and [Adding New Condition Handlers](../authorization/adding-condition-handlers.md).

---

## audit log

An append-only record of security-relevant events (an authorization decision, a login, a policy change, an account deletion). There's no update or delete API for it; it exists so an authorized policy holder can later answer "who did what, and was it allowed." See [Authorization Architecture: Audit Log](../authorization/architecture/component-responsibilities.md#audit-log).

---

## self_service policy

The default policy every newly-created account gets assigned (password signup or Google OAuth2), letting a user manage their own profile and sessions without granting anything about other accounts. See [Policy JSON Examples](../authorization/policy-examples.md).

---

## direct grant

A permission handed to one specific user directly (`UserPermission`), bypassing policies entirely. It's evaluated the same way a policy-granted action is, so a caller's overall access is the union of their assigned policies plus any direct grants. See [Adding New Permissions: Direct grants vs. policies](../authorization/adding-permissions.md#direct-grants-vs-policies).

---

## permission catalog

The read-only, built-in action reference (e.g. `policies:read`, `users:update_own`) browsable at `GET /authorization/permissions/catalog`. It is not a global allow-list: policies and direct grants may also contain opaque action strings defined by a downstream application. MysticAuth does not own or describe those app actions, but its grant guard still requires the caller to already hold every action being granted. Applications should expose their own catalog/UI for custom actions. The endpoint is available to callers who need it for read-only browsing or for policy/permission forms: any one of `permissions:read`, `policies:create`, `policies:update`, or `permissions:grant` is enough.

---

## policy history

An automatic change log kept for every policy: each create/update/delete/rollback stages a row recording what changed, in the same database transaction as the change itself. It's what powers "compare two versions of this policy" and "roll back to an earlier version." See [Writing and Testing Policies](../authorization/writing-testing-policies.md).

---

## cache-aside

A caching pattern where the app checks the cache first, and on a miss, reads the real data store (here, Postgres) and writes the result into the cache before returning it. The PBAC policy cache uses this pattern with Valkey in front of Postgres. See [Authorization Architecture](../authorization/architecture/README.md#pbac-authorization-check-request-flow).

---

## privilege escalation guard

The check (`assert_authorized_to_grant`) that stops a caller from handing out, editing, or revoking access to a sensitive action they don't already hold themselves. It applies symmetrically: granting a policy, updating one, and revoking one all run through it, not just the grant side. See [Authorization Architecture: Authorization Service](../authorization/architecture/component-responsibilities.md#authorization-service).

---

## fail-safe / fail-closed

A design where, when something goes ambiguous or breaks (an unrecognized condition key, a Valkey outage during rate limiting), the system denies access rather than allowing it by default. PBAC's condition evaluation and the rate limiter both fail this way; contrast with the PBAC Valkey policy cache, which fails open to Postgres instead (see [Infrastructure: cache-aside](infrastructure.md#cache-aside) and [Authorization Architecture: Condition Evaluation Service](../authorization/architecture/component-responsibilities.md#condition-evaluation-service)).

---

## batch authorization check

A single API call (`POST /authorization/batch-check`) that evaluates several action/resource checks for one caller at once, fetching that caller's policies only once instead of once per check. Used by frontend pages that need several permission answers at load time. See [Authorization Architecture: Authorization Service](../authorization/architecture/component-responsibilities.md#authorization-service).

---

## resource type

The category of thing a policy's actions apply to (e.g. `"users"`, `"policies"`, or `"*"` for every resource type). Combined with an action string (like `read` or `update_own`), it's what a policy actually matches against a request. See [Policy JSON Examples](../authorization/policy-examples.md).

---

## condition (policy)

An optional narrowing rule on a policy, keyed by condition type inside its `conditions` JSON field (e.g. `self_only`, `resource_attributes`, a time window). Every condition present must pass (they're AND'ed together) for the policy to grant access on a given check; an unrecognized condition key is rejected outright rather than silently ignored. See [Condition Schema Reference](../authorization/condition-schema-reference.md).

---

## self_only condition

A specific condition type that restricts a policy so it only grants access to a resource whose `email` field matches the acting user's own email, i.e. "your own records only." See [Condition Schema Reference: self_only](../authorization/condition-schema-reference.md#self_only).

---

## resource_attributes condition

A specific condition type that requires listed fields on the resource being acted on to equal expected values (e.g. only grant access when `status` is `"draft"`). See [Condition Schema Reference: resource_attributes](../authorization/condition-schema-reference.md#resource_attributes).

---

## defense in depth

A design where the same rule is enforced by more than one independent layer, so a gap in one doesn't become a real vulnerability. Policy conditions are validated both when a policy is written (rejecting bad data up front) and again when a policy is evaluated (failing safe if bad data somehow got in anyway). See [Condition Schema Reference](../authorization/condition-schema-reference.md).

---

## granular permission

A permission scoped narrowly enough to distinguish "your own" from "anyone's" (e.g. `users:update_own` vs. `users:update_any`), rather than one broad catch-all action, so a policy can grant exactly the access it means to and nothing wider.

---

## bulk operation

A PBAC management action that applies one policy assign/remove, permission grant/remove, or role change to many target users in a single request, returning a per-item success/error result rather than failing the whole batch on one bad target. See [Authorization Architecture: Full route list](../authorization/architecture/full-route-list.md#full-route-list).

---
