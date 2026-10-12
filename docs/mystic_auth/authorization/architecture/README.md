# PBAC Architecture

---

## PBAC authorization-check request flow

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Request(["Request"])
    Auth["Authentication\n current_user_dependency.py"]
    Ctx["Authorization Context Builder\n request_context_builder.py"]
    Svc["Authorization Service\n authorization_service.py"]
    Cache{"Policy Cache\n Valkey\n authorization_cache_service.py"}
    Eng["Policy Evaluation Engine\n policy_evaluator.py"]
    Cond["Condition Evaluation Service\n condition_evaluation_service.py"]
    Dec["Authorization Decision\n authorization_decision.py"]
    Log["Authorization Audit Log\n authorization_audit_log_repository.py"]
    Request --> Auth --> Ctx --> Svc --> Cache
    Cache -- "hit" --> Eng
    Cache -- "miss, fetch from Postgres,\n then cache 60s" --> Eng
    Eng --> Cond --> Dec --> Log
    classDef entry fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    classDef cache fill:#fef9c3,stroke:#ca8a04,color:#713f12
    classDef decision fill:#ede9fe,stroke:#7c3aed,color:#4c1d95
    classDef terminal fill:#f3f4f6,stroke:#6b7280,color:#1f2937
    class Request entry
    class Cache cache
    class Dec decision
    class Log terminal
    linkStyle default stroke:#334155,stroke-width:2px
```

---

Every real (non-hypothetical) authorization decision in the app goes through this exact pipeline, once. Nothing above the Authorization Service reads a user's role, a permission-role mapping, or does its own access comparison: routes only ever declare *what action on what resource type* they need. Before evaluation, the Authorization Service fetches the caller's active policies through a Valkey cache-aside layer (`authorization/repositories/policy_assignment_repository.py`), not straight from Postgres on every call. See [Troubleshooting: Valkey cache management](../troubleshooting/valkey-and-logging.md#valkey-cache-management) for TTL and invalidation rules.

---

## `users.role` is display-only, and is guarded as if it weren't

`users.role` (`user`, `admin`, `system`) never enters an authorization decision: nothing in the pipeline above reads it, so setting it to `"admin"` grants nothing by itself (see [Unconditioned Policy Quickstart](../unconditioned-policy-quickstart.md) for modeling role-shaped access with an actual policy instead). It exists purely so the UI can group/label accounts.

Being cosmetic today doesn't make it safe to leave unguarded. `PATCH /users/{email}/role` and its bulk counterpart still reject a caller trying to change **their own** role, even holding `users:assign_role`, for the same reason `assert_authorized_to_grant` stops a caller from minting themselves a policy they don't already qualify for (see [Component Responsibilities](component-responsibilities.md)): the moment any downstream project adds a single `if user.role == "admin"` shortcut (a frontend nav guard, a support script, a future endpoint that hasn't gone through PBAC yet), an unguarded self-relabel becomes a real privilege escalation, and the guard belongs at the API boundary that field is set through, not left to depend on every future caller of `role` having recreated PBAC's own escalation checks by hand. Assigning `"system"` to *anyone* still requires the separate, stronger `users:assign_system_role` action regardless of this guard.

---

## Pages

- [Component Responsibilities](component-responsibilities.md): Authentication, Authorization Context Builder, Authorization Service, Policy Evaluation Engine, Condition Evaluation Service, Authorization Decision, Audit Log.
- [Integration Points and Real-Time Push](real-time-push.md): how routes and policy mutations hook into the pipeline, and how open browser tabs learn about a permission change live.
- [Full Route List](full-route-list.md): every PBAC route and the permission it requires.
- [Frontend Policy Management UI](frontend-ui.md): the permission-protected policy and permission screens.

---
