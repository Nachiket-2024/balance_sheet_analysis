# Company Access and Onboarding Flow
---

This page follows a user from initial account access to a company-scoped
request. MysticAuth owns authentication and the PBAC engine; the app owns
company scope and its permission vocabulary.
---

## Request flow

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Browser["Signed-in browser"] --> Auth["MysticAuth session"]
    Auth --> Route["App route or API request"]
    Route --> Company["Load target company"]
    Company --> Policy["Check company_id or group_root_id policy"]
    Policy -->|allowed| Data["Read or update scoped data"]
    Policy -->|denied| Forbidden["403 response"]
    NewUser["New account"] --> Self["self_service only"]
    Self --> Grant["Admin assigns an app policy"]
    Grant --> Policy
    classDef success fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    class Data,Grant success
    class Forbidden blocked
    class Policy decision
```
---

## Ownership and code

---

| Step | File | Role |
|---|---|---|
| Authenticate the request | `backend/mystic_auth/` | Validates the session and exposes the current user. |
| Define app actions | `backend/app/access/permissions.py` | Names company, balance-sheet, and LLM actions. |
| Build company scope | `backend/app/access/scope.py` | Filters list queries or checks one resource against company/group policy attributes. |
| Enforce a route | `backend/app/api/` | Requires the action before returning protected app data. |
| Render protected UI | `frontend/src/app/App.tsx` and shared MysticAuth guards | Hides unavailable navigation and blocks direct route access. |

A new account receives MysticAuth's `self_service` policy only. An administrator
must assign an app policy before the user can see company data. A role value is
display metadata and does not grant access.
---

## See also

---

- [Access-control overview](../access-control/overview.md)
- [Enforcement paths](../access-control/enforcement.md)
- [Onboarding a real user](../access-control/onboarding.md)
- [Roles are metadata](../access-control/roles-are-metadata.md)
