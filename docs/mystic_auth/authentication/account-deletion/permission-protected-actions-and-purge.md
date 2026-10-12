# Account Deletion: Permission-Protected Actions and Purge

---

## Permission-protected actions

All under `backend/mystic_auth/api/user_routes/user_lifecycle_routes.py`, mounted at `/users`:

| Route | Permission | Effect |
|---|---|---|
| `DELETE /users/{email}` | `users:deactivate_any` | Soft-delete: same routine as self-service, permission-protected audit event (`account_deleted`). Same bump-failure handling as self-delete: the soft-delete always succeeds, an unconfirmed revoke is logged critical and recorded as `sessions_revoked_confirmed: false` in the audit metadata rather than erroring the request |
| `PATCH /users/{email}/reactivate` | `users:reactivate` | Clears `is_active`/`deleted_at`; the only way to recover a soft-deleted account, whether self-deleted or deleted through a permission-protected route |
| `DELETE /users/{email}/purge` | `users:delete_any` | Irreversible hard delete via the shared `purge_user_account()` |

`users:delete_any` is a distinct, more sensitive permission from `users:deactivate_any`, granted only by the
seeded `system_superuser` policy: a caller who can delete accounts day to day cannot irreversibly
destroy one. Both permission-protected routes reject the system account and the caller's own account as targets
(a caller purging themselves through this route would be an unrecoverable lockout);
self-service delete has no such guard, since acting on your own account is the entire point.

---

## Purge: manual and scheduled

`user_lifecycle/user_purge_service.py::purge_user_account(user, db, *, purged_by, request=None)` is
the one routine both purge paths call, so they can never drift apart:

1. Revoke every session on the account. Unlike every other revoke-adjacent path in the app, this
   one **fails closed**: revocation happens before the irreversible hard delete below, so if the
   bump can't be confirmed (Postgres unavailable), `purge_user_account` raises
   `TokenVersionUnavailableError` and nothing past this step runs - no audit write, no delete. See
   [Bump failure handling](../session-management/token-lifecycle.md#bump-failure-handling) for why this one path is
   the exception to "the primary action still succeeds."
2. Anonymize the account's historical security and authorization audit rows. The event types,
   actions, outcomes, and timestamps remain, but the email, IP, user-agent, and authorization
   context that could identify the account are stripped or replaced with a deleted-account sentinel.
3. Write the `account_purged` security audit event, **before** the row is deleted, since that event
   is what makes the irreversible action reviewable afterward.
4. Hard-delete the row. `user_policies` rows cascade-delete (`ON DELETE CASCADE`); the anonymized
   audit rows remain as aggregate history rather than a foreign-key dependency on the deleted user.

---

## Purge flow

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Privileged["Authorized caller: DELETE /users/{email}/purge"]
    subgraph Scheduled["Daily 03:00 UTC"]
        Cron["procrastinate_tasks/\n account_purge_tasks.py"]
        Query["get_deleted_before\n (now - ACCOUNT_PURGE_GRACE_DAYS)"]
        Cron --> Query
    end
    Privileged --> Purge["purge_user_account()"]
    Query --> Purge
    Purge --> Revoke["Revoke sessions"]
    Revoke -- "confirmed" --> Audit["Audit: account_purged"] --> HardDelete["Hard delete row"]
    Revoke -- "Postgres unavailable" --> Blocked["Raises, nothing deleted.\n Manual: 503 SESSION_REVOCATION_UNAVAILABLE.\n Scheduled: that account skipped,\n retried on tomorrow's run."]
    linkStyle default stroke:#334155,stroke-width:2px
```

---

The scheduled job (`account_purge_tasks.py::purge_expired_soft_deleted_accounts`) is registered via
`@app.periodic(cron="0 3 * * *")` and deferred automatically by the Procrastinate worker's own
internal periodic-task deferrer: no separate scheduler process is involved (see
[Background Email Delivery](../../background-workers/procrastinate.md)). It queries
`user_lifecycle_crud.get_deleted_before(cutoff)` for every account whose `deleted_at` predates
`now - settings.ACCOUNT_PURGE_GRACE_DAYS` (default 30 days) and purges each one with
`purged_by="system:grace_period_purge"`. This is what gives self-service deletion (and permission-protected
soft-delete) an actual recovery window, restorable via `PATCH /users/{email}/reactivate` for the
whole grace period, instead of either purging synchronously (no recovery at all) or accumulating
soft-deleted rows forever.

---

See [Account Deletion](README.md) for the feature map, or [Self-Service Paths](self-service.md)
for the user-initiated flows.

---
