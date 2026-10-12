# PBAC Architecture: Component Responsibilities

---

### Authentication
`auth/current_user/current_user_dependency.py`'s `get_current_user` verifies the `access_token` cookie and returns `{name, email, role}`. Authentication answers *who is calling*; it never answers *what they're allowed to do*. `role` here is metadata only: see [Adding New Permissions](../adding-permissions.md) for why role never grants access.

---

### Authorization Context Builder
`authorization/context/request_context_builder.py`'s `build_authorization_context(request)` produces the one `context` dict every real authorization check evaluates conditions against:

```python
{
    "ip_address": "203.0.113.7",       # resolved via auth/security/client_ip.py
    "current_time": "2026-07-13T12:00:00+00:00",  # this server's own clock
    "security_context": {},             # reserved for a future trust-signal layer
}
```

**Rule: never trust client-supplied values by default.** `ip_address` is resolved by `auth/security/client_ip.py::get_client_ip`: the literal TCP peer (`request.client.host`) unless the peer itself is listed in `TRUSTED_PROXY_IPS` (`.env`, empty/untrusted by default), in which case the left-most `X-Forwarded-For` entry is trusted instead. `current_time` always comes from this backend's own clock, never anything in the request body or headers. The one deliberate exception is the authorization-check *inspection* endpoint (`POST /authorization/users/{email}/authorization-check`), which accepts a caller-supplied `context` on purpose: it's a "what would happen if" simulation tool for authorized policy users, not a real access decision, so there's nothing to spoof.

---

### Authorization Service
`authorization/services/authorization_service.py`. The single entry point every route/service calls:

- `authorize(user_email, action, resource_type, db, resource=None, context=None) -> bool`: the common case. Thin wrapper over `authorize_with_decision`.
- `authorize_with_decision(...) -> AuthorizationDecision`: computes the decision and writes an audit log entry. `authorize()` is just `.allowed` off of this.
- `authorize_detailed(...) -> AuthorizationDecision`: same computation, **no audit log write**. Used by the policy inspection endpoint and by `authorize_with_decision` internally, so a hypothetical "what if" query never pollutes the real audit trail.
- `authorize_batch(user_email, checks, db, context=None) -> list[AuthorizationDecision]`: fetches the user's policies **once** and evaluates every check against that same list, logging each decision individually. Used by `POST /authorization/batch-check`.
- `require(...)`: same as `authorize()`, but raises `HTTPException(403)` instead of returning `False`. This is what `dependencies/authorization_dependency.py`'s `require_authorization(action, resource_type)` factory calls: the dependency every protected route depends on.
- `assert_authorized_to_grant(caller_email, actions, resource_type, db)`: the privilege-escalation guard. Before a policy create, update, assignment, direct grant, or revoke can change access, the caller must already hold every action involved. This applies to MysticAuth's built-in actions and opaque downstream application actions. The protected `system_superuser` policy is the trusted bootstrap exception. The implementation is `authorization/services/authorization_grant_guard.py::assert_authorized_to_grant`, a standalone function rather than a method on this class, imported locally inside it to avoid a circular import (`authorization_grant_guard` itself calls back into `AuthorizationService.authorize` to check what the caller holds); `AuthorizationService` re-exposes it as a static method so existing `authorization_service.assert_authorized_to_grant(...)` call sites don't change. Applied symmetrically, not just on the grant side: `update_policy` and `delete_policy` (`policy_crud_routes.py`) call it with the policy's *current* actions/resource_type before touching it at all, and `remove_policy_from_user` (revoke, `policy_assignment_routes.py`) calls it the same way before removing an assignment. Without the symmetric half, bare `policies:delete`/`update`/`revoke` (without holding what the policy actually grants) could strip, narrow, or repurpose an equally- or more-privileged peer's access, including revoking `system_superuser` off someone else, with no escalation check at all.

---

### Policy Evaluation Engine
`authorization/evaluators/policy_evaluator.py`'s `PolicyEvaluationEngine`. Pure and DB-free: given a user's already-fetched policies plus `(action, resource_type, resource, context)`, it:

1. Filters to policies whose `resource_type` matches (or is `"*"`).
2. Filters to policies whose `actions` list contains the requested action.
3. For each matching candidate, delegates the whole `conditions` block to the Condition Evaluation Service.
4. Builds an `AuthorizationDecision`: `allowed` is `True` iff at least one candidate's conditions passed.

The engine has **zero condition-specific logic**. It doesn't know what `"time"` or `"self_only"` mean: see [Adding New Condition Handlers](../adding-condition-handlers.md) for why that separation is deliberate.

**A conditioned grant is not a hard ceiling on an action.** Step 4's "at least one" is a pure OR across *every* policy and direct permission a user holds for that `(action, resource_type)` pair, whether or not it's conditioned. So if a user holds both a conditioned grant (e.g. business-hours-only) and any other unconditioned grant for the identical action - a policy, a direct permission, added by a different admin, at a different time, for an unrelated reason - the conditioned one's restriction is silently moot for them, with no warning anywhere in the UI or API. Run `python -m mystic_auth.scripts.report_conditioned_grant_conflicts` to list every user this currently applies to; it's read-only and changes no authorization behavior.

---

### Condition Evaluation Service
`authorization/conditions/condition_evaluation_service.py`. Dispatches each key in a policy's `conditions` dict to its registered handler (`authorization/conditions/condition_registry.py`) and ANDs the results. An unrecognized condition key **fails safe (denies)** rather than being silently ignored: a policy can never grant access via a condition the engine doesn't understand.

---

### Authorization Decision
`authorization/evaluators/authorization_decision.py`'s `AuthorizationDecision`: the explainable result object:

| Field | Meaning |
|---|---|
| `allowed` | The final decision. |
| `evaluated_policies` | Every policy's name the engine was given, regardless of match. |
| `matched_policies` | Matched action+resource_type **and** conditions passed: what actually granted access. |
| `rejected_policies` | Matched action+resource_type but conditions failed. |
| `failed_conditions` | `{policy_name: [condition_key, ...]}` for every rejected policy. |
| `denial_reason` | `None` if allowed; else `"no_assigned_policies"`, `"no_matching_policy"`, or `"condition_failed"`. |
| `evaluation_timestamp` | ISO 8601 UTC, this server's clock. |

---

### Policy Action Revocation
A policy assignment is otherwise all-or-nothing: revoking it drops every action the policy grants that user, even ones they should keep. `authorization/services/policy_action_revocation_service.py`'s `PolicyActionRevocationService.revoke_single_action` exists for "take exactly one action away from one user, leave the rest of that policy's grant intact" - editing the policy definition itself isn't an option, since that would affect every other holder of the same policy.

Implementation: in one transaction, remove the user's `UserPolicy` assignment row entirely, then re-create (or reactivate) a direct `UserPermission` grant for each of the policy's *other* actions, carrying over the assignment's `conditions` so the user's effective access is unchanged except for the one revoked action. Raises `ActionNotInPolicyError` if the requested action isn't one of the policy's own `actions` - there is nothing to carve out.

Exposed as `POST /authorization/users/{email}/policies/{name}/revoke-action` (`api/pbac_routes/policies/policy_assignment_routes.py`). Requires **both** `policies:revoke` (this ends the policy assignment) and `permissions:grant` (this creates the replacement direct grants) - a caller holding only one of the two could otherwise use this route to do half of what either dedicated route alone would refuse. The caller-holds-what-they-grant escalation guard (same as `remove_policy_from_user`) is checked against the policy's *full* action set, not just the actions being kept, and the `system_superuser` last-assignment lockout guard applies the same way it does to a plain revoke, since this still ends that one assignment row.

---

### Audit Log
`authorization/repositories/authorization_audit_log_repository.py` + the `authorization_audit_log` table. Every `authorize()`/`authorize_with_decision()`/`authorize_batch()` call writes one row: `allowed`, `candidate_policy_names`, `granting_policy_names`, `failed_conditions`, and the `context` it was evaluated against. Append-only; no update/delete API exists for it. Query via `GET /authorization/audit-log` (requires `policies:read`), `GET /authorization/audit-log/users/{email}` (requires `policies:read`), or `GET /authorization/audit-log/me` (any authenticated caller, their own entries only).

For a single decision (`authorize()`/`authorize_with_decision()`), the row is not written inline: `_log_decision` queues it via `log_authorization_decision_task` (`procrastinate_tasks/audit_log_tasks.py`), and a Procrastinate worker performs the actual insert. `authorize()` itself only waits on the (small, cheap) enqueue, not on the audit row's write; the write is picked up over Postgres `LISTEN/NOTIFY`, typically landing in well under a second. This keeps every protected route's response latency independent of the audit-log commit, which the response never depended on in the first place, while still giving the write Postgres-backed durability (a worker crash retries the job rather than losing the entry, unlike an in-process fire-and-forget task). `authorize_batch()` still writes its rows inline, one bulk insert per batch, since a batch request is already amortizing the cost across up to 50 checks.

---

See [PBAC Architecture](README.md) for the request flow, or [Integration and Real-Time Push](real-time-push.md) for how the rest of the app hooks into this pipeline.

---
