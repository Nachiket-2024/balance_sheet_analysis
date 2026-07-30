# Architecture: The `app/` vs `mystic_auth/` Split, in Practice

```
backend/
  mystic_auth/        <- template internals, never edited (auth, PBAC engine, audit log, users)
  app/
    main.py           <- FastAPI app: mounts mystic_auth's routers, then this app's own
    sdk.py            <- template's own re-export surface (unedited, as shipped)
    app_sdk.py         <- THIS app's re-export surface: mystic_auth internals this app
                          additionally needs (policy_repository, Base, rate_limiter_service)
    access/            permissions.py (action vocabulary) + scope.py (the company-hierarchy
                        scoping logic, see ../access-control/overview.md)
    companies/          Company model/schema/crud (no routes, see api/ below)
    balance_sheets/      BalanceSheet model/schema/crud, yfinance import logic
    llm/                grounded LLM chat (schema/service/config)
    api/                routes ONLY, mirroring mystic_auth/api/'s own layout:
      company_routes/company_routes.py
      balance_sheet_routes/balance_sheet_routes.py
      llm_routes/llm_routes.py
    seed/               seed_base_policies.py: runs automatically, baseline unconditioned
                        role policies (see ../access-control/baseline-policies.md);
                        seed_demo_data.py: opt-in, disposable demo companies/users/scoped-policies
  alembic/              ONE shared migration history for mystic_auth's + this app's tables
                        (see env.py: both sets of models import into the same target_metadata)

frontend/
  src/mystic_auth/     <- template internals, never edited (login, PBAC hooks, layout shell)
    api/                mystic_auth's own axios clients (axiosInstance.ts, users_api.ts, ...)
  src/app/
    sdk.ts             <- template's own re-export surface (unedited, as shipped)
    app_sdk.ts          this app's own re-export surface: currently just DashboardPage,
                        the one piece sdk.ts doesn't already cover (see sdk-and-extension-points.md)
    access/             permissions.ts, mirrors backend/app/access/permissions.py's action
                        strings; deliberately its own folder, not mystic_auth/authorization/
                        (see conventions.md)
    api/                axios clients ONLY, mirroring mystic_auth/api/'s own layout:
      company_api.ts, balance_sheet_api.ts, llm_api.ts (no components/hooks here)
    companies/          list/detail pages + react-query hooks (companyQueries.ts)
    balance-sheets/      chart + table + import/delete UI + react-query hooks
    llm/                chat widget
    App.tsx             THIS app's routing: mounts mystic_auth's auth pages/layout plus
                        this app's own routes, and renders mystic_auth's own DashboardPage
                        directly at "/dashboard" (see sdk-and-extension-points.md)
```

See [Features](../features.md) for the LLM chat and yfinance-import implementation notes, and [Syncing with upstream](../syncing.md) for how `mystic_auth/` itself gets updated.

## See also

- [Conventions](conventions.md): why routes/API clients/access code are split the way they are
- [SDK and Extension Points](sdk-and-extension-points.md): the `sdk`/`app_sdk` split, and how the sidebar/dashboard extend mystic_auth's shared chrome without editing it
