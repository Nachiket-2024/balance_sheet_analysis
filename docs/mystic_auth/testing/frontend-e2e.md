# Frontend Browser E2E Tests
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

These 27 Playwright specs exercise the application in a real browser. “Mocked”
means the browser receives deterministic route fixtures. “Real disposable
account” means the test creates or uses a short-lived account against the local
stack. “Real seeded accounts” means the test depends on the PBAC matrix seeded
by `local-scripts/mystic_auth/seed-user-permission-matrix.py`. “Live” is opt-in.

The CI browser run uses two workers and two retries. Mocked UI and authorization
checks run in all four browser projects. The real-account matrix runs
exhaustively in Chromium desktop, where it checks live database grants without
multiplying login and route traffic across four engines. The responsiveness
timing suite runs in Chromium desktop and mobile; Firefox and WebKit still run
the broader layout, accessibility, and interaction suites. This split keeps
the shared disposable backend deterministic without relaxing the 30-second
test timeout or performance assertions. Set `PLAYWRIGHT_WORKERS` when
deliberately validating on a larger runner; the browser fixture also accepts
`PLAYWRIGHT_COMPOSE_PROJECT_NAME` for an isolated Compose stack.
For a native run without an already booted frontend container, set
`PLAYWRIGHT_USE_PREVIEW=1` to build once and serve the production bundle via
Vite preview, avoiding dev-server HMR noise during the browser matrix.

If the browser frontend is served from a non-default host/port, set matching
`FRONTEND_BASE_URL`/`FRONTEND_ADDITIONAL_BASE_URLS` and `VITE_API_BASE_URL` in
Compose. The backend must allow the actual browser origin; otherwise a valid
login is followed by an apparent `/login` redirect and the later audit-log
layout failure is only a downstream symptom.

## Persistent local accessibility operator

For manual browser, keyboard, and Lighthouse checks against the local dev
stack, run `tests/scripts/mystic_auth/accessibility/seed-accessibility-user.sh` once
after the stack is up. It creates or refreshes this local-only account and
assigns the self-service, user-management, and system-superuser policies:

The email and password are stored only in the ignored local file
`.local/accessibility-operator.env`. Create that file with
`ACCESSIBILITY_OPERATOR_EMAIL` and `ACCESSIBILITY_OPERATOR_PASSWORD` before running
the seed command. It is not copied into Docker images or Compose environment
files.

The command marks the account verified and active, hashes the password in the
backend, and forces `EMAIL_ENABLED=false` for the seed process. The checked-in
local environment already has `EMAIL_ENABLED=false`; do not use these dummy
credentials against a production deployment.

For a human Linux screen-reader pass, run this from the graphical session that
owns the browser and has working audio:

```bash
dbus-run-session -- orca --replace
```

Orca must be able to see the browser's AT-SPI application. A terminal-only
session, a headless browser, or a host without an audio device is not a
screen-reader listening pass. Test signup, login, and one CRUD flow, including
icon-button labels, route changes, dialog focus, Escape, and focus return.

Verify the account directly in Postgres rather than trusting the seed output:

```bash
docker compose -f docker/mystic_auth/compose/docker-compose.dev.yml \
  -f docker/app/compose/docker-compose.dev.yml \
  --env-file env/mystic_auth/.env.dev --env-file env/app/.env.dev \
  exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT u.email, u.role, u.is_verified, u.is_active, count(up.policy_id) AS policy_count FROM users u LEFT JOIN user_policies up ON up.user_id = u.id WHERE u.name = 'Accessibility Test Operator' GROUP BY u.email, u.role, u.is_verified, u.is_active;"
```

The expected result is one verified, active `system` user with three assigned
policies. The account is intentionally persistent for repeated local browser sessions;
remove it from the local database when it is no longer needed.

---

## App and public pages

- `tests/frontend/app/e2e/landing/landing_page_browser.spec.ts` verifies the
  public landing route, visible content, and responsive browser rendering. Its
  title check follows the configured `APP_NAME` through the landing page's
  brand link, so downstream applications can use their own name instead of
  inheriting a literal `MysticAuth` assertion.
- `tests/frontend/app/e2e/legal/legal_pages_browser.spec.ts` verifies each
  legal page in real browser projects and checks navigation/rendering.
- `tests/frontend/app/e2e/status_pages/status_pages_browser.spec.ts` verifies
  status, not-found, and not-authorized pages and their browser navigation.
- `mystic_auth/e2e/public/public_pages_browser.spec.ts` verifies only
  mystic_auth-owned behavior reachable from a public page: the shared
  ControlCluster component's interactive state (theme/font-size/language),
  the login page's own legal-link wiring and back-navigation, and the
  authenticated-root-redirect route guard. It deliberately never asserts
  against landing/legal/status-page content, since that's app-owned and
  already covered by the three specs listed above it.

## Authentication and account settings

- `auth/auth_pages_responsive_browser.spec.ts` checks auth layouts at narrow
  widths and guards against mobile overflow. Backend mode: mocked.
- `auth/login_and_logout_browser_flow.spec.ts` creates or uses a disposable
  account to verify login, protected navigation, logout, and logout-all.
- `auth/signup_and_verification_browser_flow.spec.ts` verifies signup,
  validation, verification-request, and verification-result browser states.
  Backend mode: mocked endpoints.
- `auth/password_reset_browser_flow.spec.ts` verifies reset request, token
  confirmation, validation, cooldown, and navigation. Backend mode: mocked.
- `auth/oauth2_login_browser_flow.spec.ts` verifies OAuth redirect, callback
  errors, cancellation, and retry states. Backend mode: mocked OAuth.
- `auth/protected_route_redirect_browser.spec.ts` verifies unauthenticated and
  unauthorized redirects and return-route behavior. Backend mode: mocked auth.
- `auth/preauth_keyboard_and_confirmation_browser.spec.ts` verifies keyboard-
  only pre-auth controls, focus order, and confirmation interactions.
- `account_settings/account_settings_page_browser.spec.ts` verifies settings
  tabs, profile/password/appearance controls, deletion dialog, and overflow.
  Backend mode: mocked API.
- `account_settings/confirm_delete_account_browser_flow.spec.ts` verifies the
  deletion-confirmation token page for valid, missing, and invalid tokens.
  Backend mode: mocked endpoint.

## Authenticated pages

- `dashboard/dashboard_page_browser.spec.ts` verifies dashboard controls,
  responsive layout, loading/data states, and least-privilege redirects.
  Backend mode: mocked API.
- `dashboard/active_sessions_browser.spec.ts` verifies session cards, revoke
  actions, confirmation dialogs, and focus restoration. Backend mode: mocked.
- `users/users_page_browser.spec.ts` verifies user tables, filters, row/bulk
  dialogs, escaped content, and permission gates. Backend mode: mocked API.
- `policies/policies_page_browser.spec.ts` verifies policy lists/forms,
  filters, dialogs, keyboard behavior, and permission gates. Mocked API.
- `permissions/permissions_page_browser.spec.ts` verifies catalog listing,
  details, filters, and permission gates. Backend mode: mocked API.
- `rate_limits/rate_limits_page_browser.spec.ts` verifies rate-limit listing,
  filters, reset confirmation, and permission gates. Mocked API.
- `audit_log/audit_log_page_browser.spec.ts` verifies audit categories, scope,
  filters, pagination, details, and tab behavior. Mocked API.
- `layout/app_shell_controls.spec.ts` verifies sidebar/navbar, command palette,
  theme/language/font controls, responsive menu, shortcuts, and Escape.
- `accessibility/accessibility_browser.spec.ts` runs axe WCAG 2.1 AA checks
  over public and authenticated major pages. Backend mode: mocked API.

## Authorization matrix

- `authorization/permission_matrix_browser.spec.ts` exercises nine mocked
  permission profiles across protected routes, controls, dialogs, focus
  restoration, and fail-closed states. It proves broad frontend gating with
  synthetic `/auth/me` responses.
- `authorization/permission_matrix_real_accounts_browser.spec.ts` exercises
  the seeded real-account matrix in Chromium desktop. It checks exact
  `/auth/me` permission sets, route gates, authorization-log “All users”
  visibility, and the Security Events “All users” tab for
  `security_audit:read`. The seed currently creates 40 role/policy/direct-grant
  combinations, of which 32 verified-active buckets are selected for browser
  coverage. The mocked matrix covers the same frontend gates in every browser
  project, so the live matrix is not duplicated against the shared backend.
  WebKit and Firefox can expose the login response before the `Set-Cookie`
  commit is observable to a subsequent request. The test polls `/auth/me` until
  the authenticated contract is visible, and waits on rendered route state
  rather than fixed sleeps. That is a browser fixture timing race, not a
  permission failure; failures after the bounded poll are actionable.

## Performance and live deployment

- `performance/management_responsiveness_browser.spec.ts` checks delayed permission-management
  tables, repeated destructive confirmation, filtering, sorting, and browser
  responsiveness in Chromium desktop and mobile. Backend mode: mocked API.
- `performance/core_web_vitals_browser.spec.ts` is an opt-in Chromium baseline
  for LCP plus an interaction timing sample on the dashboard and audit log.
  Run it with `RUN_FRONTEND_PERF=1`; optional `FRONTEND_LCP_BUDGET_MS` and
  `FRONTEND_INP_BUDGET_MS` turn measured budgets into assertions. It is not a
  blocking CI gate because local lab measurements are not production RUM.
- `live/live_deployment_smoke.spec.ts` verifies real signup/login, inert stored
  XSS, protected redirects, and 390px overflow against `LIVE_BASE_URL`. It is
  skipped unless the live environment variables are supplied. Run it against a
  disposable local-prod stack with the Chromium project explicitly selected:

  ```bash
  LIVE_BASE_URL=http://127.0.0.1:8180 \
  LIVE_POSTGRES_CONTAINER=mystic-auth-local-prod-ngrok-postgres-1 \
  npm exec --prefix frontend playwright -- test \
    tests/frontend/mystic_auth/e2e/live/live_deployment_smoke.spec.ts \
    --config=frontend/playwright.config.ts --project=chromium-desktop --workers=1
  ```

  The permission assertion uses a browser `fetch` with `credentials: "include"`
  so it validates the same cookie/proxy path used by the UI, including when the
  production bundle uses a relative API base URL. The test creates disposable
  accounts and updates verification state only in the specified local Postgres
  container; never point it at production data.

---

## See also

- [Frontend Test Map](frontend.md)
- [Frontend Integration Tests](frontend-integration.md)
- [Testing Overview](overview.md)
