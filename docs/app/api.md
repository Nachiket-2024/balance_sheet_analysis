# API Reference: This App's Endpoints

mystic-auth's own endpoints (`/auth/*`, `/users/*`, `/authorization/*`,
`/audit/*`, `/health/*`) are documented under
[`../mystic_auth/api/`](../mystic_auth/api/), unchanged by this project.
Everything below is defined in `backend/app/`.

All endpoints require an authenticated session (the `access_token` cookie
mystic-auth's login sets) and enforce PBAC per
[Access Control](access-control/overview.md); a company/balance-sheet/LLM request
outside the caller's scope returns `403`, not a filtered/empty `200`.

## Companies (`backend/app/api/company_routes/company_routes.py`)

| Method | Path                | Action checked   | Notes                                                                 |
|--------|---------------------|-------------------|------------------------------------------------------------------------|
| GET    | `/companies/`        | `company:read`     | Every company the caller's policies grant; see [Enforcement](access-control/enforcement.md)'s list-endpoint scoping. |
| POST   | `/companies/`         | `company:create`   | `{name, ticker, parent_company_id?}`. Omit `parent_company_id` for a group root; `group_root_id` is computed automatically. |
| GET    | `/companies/{id}`     | `company:read`     | 404 if the company doesn't exist, 403 if it exists but is outside the caller's scope. |
| DELETE | `/companies/{id}`     | `company:delete`   | Cascades to delete every balance sheet on file for it (`BalanceSheet.company_id` is `ON DELETE CASCADE`). 400 if it has subsidiary companies (`parent_company_id` is `ON DELETE SET NULL`, not `CASCADE`, so a subsidiary's `group_root_id` would otherwise point at a company that no longer exists); delete or reassign those first. |

## Balance sheets (`backend/app/api/balance_sheet_routes/balance_sheet_routes.py`)

| Method | Path                                | Action checked         | Notes                                                                 |
|--------|--------------------------------------|--------------------------|--------------------------------------------------------------------------|
| GET    | `/balance-sheets/company/{company_id}` | `balance_sheet:read`      | Every fiscal year on file for one company.                              |
| GET    | `/balance-sheets/{company_id}/{year}`  | `balance_sheet:read`      | One fiscal year.                                                        |
| POST   | `/balance-sheets/{company_id}/{year}`  | `balance_sheet:import`    | Fetches from yfinance using the company's `ticker` and persists it. 400 if a row for that year already exists, or yfinance has no data for it; 502 if the yfinance fetch itself fails (network error, Yahoo API error, timeout; see [Features](features.md#yfinance-needs-a-browser-impersonating-timeout-bounded-session)). Rate-limited (per-IP and per-account); each call is a real outbound yfinance request. |
| DELETE | `/balance-sheets/{company_id}/{year}`  | `balance_sheet:delete`    | 404 if no such row.                                                     |

Response fields: `id`, `company_id`, `year`, `created_at`, plus ~68 nullable
float fields (one per yfinance balance-sheet line item; see
`backend/app/balance_sheets/balance_sheet_model.py`).

## LLM chat (`backend/app/api/llm_routes/llm_routes.py`)

| Method | Path         | Action checked | Notes |
|--------|--------------|------------------|-------|
| POST   | `/llm/chat`   | `llm:chat`        | `{company_id, years?, question}` -> `{answer}`. `years` omitted = every year on file for that company. The real balance-sheet figures are injected into the LLM prompt (see `llm_service.build_grounding_context`), so the answer is grounded, not speculative. Rate-limited (per-IP and per-account); each call is a real Groq API request. |

## Rate limiting

The LLM chat and balance-sheet import endpoints reuse mystic_auth's own
Redis-backed `rate_limiter_service` (the same one gating `/auth/login`,
`/auth/signup`, etc.; see
[`../mystic_auth/security/hardening.md`](../mystic_auth/security/hardening.md)),
limited per-IP and independently per-account, at the same
`MAX_REQUESTS_PER_WINDOW`/`REQUEST_WINDOW_SECONDS` settings as the rest of
the app. A caller over the limit gets `429`. Every other endpoint in this
app (company/balance-sheet reads, company create) is not rate-limited beyond
whatever reverse proxy/infra limit you put in front of it in production;
they don't call an external paid API per request the way chat/import do.

## Action vocabulary

See `backend/app/access/permissions.py` (Python) /
`frontend/src/app/access/permissions.ts` (TypeScript) for the exact string
constants: `company:read`, `company:create`, `company:delete`,
`balance_sheet:read`, `balance_sheet:import`, `balance_sheet:delete`, `llm:chat`.
