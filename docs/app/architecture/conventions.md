# Architecture: Conventions
---
See [Overview](overview.md) for the directory tree these rules produce.
---

## Keep API clients separate from feature state and views

---

MysticAuth keeps raw Axios functions in `frontend/src/mystic_auth/api/` and
feature pages, hooks, and dialogs in separate folders. This app follows the
same split: `frontend/src/app/api/` contains the company, balance-sheet,
analysis, statement, LLM, and review clients. React Query hooks and pages stay
under `companies/`, `balance-sheets/`, `financial-statements/`, `llm/`, and
`reviews/`.
---

## Keep app permissions separate from MysticAuth authorization

---

`frontend/src/app/access/permissions.ts` and `backend/app/access/permissions.py`
define this product's action strings, including `company:read`,
`balance_sheet:import`, `llm:chat`, and `llm:usage_read_all`. MysticAuth's
`authorization/` folders implement the shared enforcement mechanism (`IfCan`,
`ProtectedRoute`, `useAuthorization`, and the authorization service). The app
uses that mechanism through its SDK and does not duplicate it.
---

## Keep routes thin and domain code outside the HTTP layer

---

MysticAuth separates domain logic from HTTP routes. The app follows the same
pattern: `companies/`, `balance_sheets/`, `financial_statements/`, `reviews/`,
and `llm/` contain models, schemas, CRUD, and services; request handlers live
under `app/api/<feature>_routes/<feature>_routes.py`.

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Request[HTTP request] --> Route[App feature route]
    Route --> Scope[App access scope and action]
    Route --> Domain[Feature service or CRUD]
    Domain --> Database[(PostgreSQL)]
    classDef success fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    class Request,Route,Scope,Domain,Database success
```

`app_sdk.py` re-exports selected MysticAuth internals needed by app domain
modules, including the shared declarative `Base`. It must not import app
routers or domain modules: that would create a cycle through the models.
`main.py` mounts app routers directly from their route modules.
---

## See also

---

- [Architecture index](README.md)
- [App documentation](../README.md)
- [SDK and Extension Points](sdk-and-extension-points.md)
