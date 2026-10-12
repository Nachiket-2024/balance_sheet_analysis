# Frontend Authentication Test Detail
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

These tests explain what the browser shows while authentication moves through
loading, success, failure, refresh, logout, verification, OAuth, and password
reset states. API-client tests prove request shape; component tests prove one
control; integration and browser tests prove the user-visible flow.

---

## API clients and auth state

- `tests/frontend/mystic_auth/unit/api/loginApi.test.ts` verifies login method,
  URL, credentials body, and typed failure conversion.
- `unit/api/logoutApi.test.ts` verifies logout/logout-all request endpoints.
- `unit/api/getCurrentUserApi.test.ts` verifies `/auth/me` response typing and
  failure handling.
- `unit/api/oauth2Api.test.ts` verifies provider list/redirect URL construction.
- `unit/api/signupApi.test.ts` verifies signup payload and API errors.
- `unit/api/passwordResetApi.test.ts` verifies reset request and confirmation
  bodies, token forwarding, and errors.
- `unit/api/verifyAccountApi.test.ts` verifies verification-email and token
  confirmation requests.
- `unit/auth/current_user/useCurrentUserQuery.test.tsx` verifies current-user
  query loading, success, errors, cache, and logout-related state.
- `unit/auth/session_lifecycle/setupAuthInterceptor.test.tsx` verifies a 401
  triggers one coordinated refresh, retries the original request, and logs out
  on refresh failure.
- `unit/auth/session_lifecycle/crossTabRefresh.test.ts` verifies other tabs do
  not duplicate refresh work and receive the resulting session state.
- `unit/auth/session_lifecycle/useSessionEventsStream.test.tsx` verifies SSE
  revoke events invalidate session/current-user data and permission changes
  clear stale permissions before refetch.

---

## Forms and password policy

- `unit/auth/auth_page_mobile_overflow.test.tsx` verifies auth pages remain
  usable at narrow widths without horizontal overflow.
- `unit/auth/signup_form_legal_consent.test.tsx` verifies required consent is
  enforced before signup submission.
- `unit/auth/password_rules/passwordRules.test.ts` verifies each password
  predicate and boundary value.
- `unit/auth/password_rules/PasswordRulesChecklist.test.tsx` verifies each
  rule's passed/failed accessible status.
- `unit/auth/password_rules/PasswordStrengthPanel.test.tsx` verifies strength
  labels and guidance for weak through strong input.
- `unit/auth/password_reset_request_form.test.tsx` verifies validation,
  non-disclosing success, pending state, and cooldown.
- `unit/auth/password_reset_confirm_form.test.tsx` verifies token/password
  validation, pending, success, and error states.
- `unit/auth/verify_account/verification_email_request_form.test.tsx`
  verifies verification-email validation, submit state, success, and failure.
- `unit/auth/verify_account/verify_account_button.test.tsx` verifies token
  verification states and navigation.
- `unit/auth/oauth2/OAuth2LoginButton.test.tsx` verifies provider selection,
  disabled state, and redirect initiation.
- `integration/auth/password_policy_consistency.test.tsx` compares the rules
  used by signup and reset-confirm forms to the backend policy contract, so a
  frontend-only password relaxation cannot ship silently.

---

## Rendered login, logout, and redirect flows

- `integration/auth/login_page.test.tsx` verifies the login form stays mounted
  throughout submission, preserves input/error behavior, and does not navigate
  prematurely while authentication is pending.
- `integration/auth/auth_flow.test.tsx` verifies login success/failure,
  current-user loading, protected navigation, logout, refresh, and auth-store
  transitions with mocked API responses.
- `e2e/auth/login_and_logout_browser_flow.spec.ts` verifies the same critical
  path with a disposable real account: login, protected route access, logout,
  and logout-all.
- `e2e/auth/protected_route_redirect_browser.spec.ts` verifies anonymous and
  unauthorized route redirects, including return-route behavior.
- `e2e/auth/auth_pages_responsive_browser.spec.ts` verifies auth layout at
  narrow/desktop sizes.
- `e2e/auth/preauth_keyboard_and_confirmation_browser.spec.ts` verifies
  keyboard-only pre-auth interaction and confirmation focus behavior.
- `e2e/auth/signup_and_verification_browser_flow.spec.ts` verifies signup and
  verification browser states with mocked endpoints.
- `e2e/auth/password_reset_browser_flow.spec.ts` verifies reset request,
  confirmation, invalid token, validation, and cooldown states.
- `e2e/auth/oauth2_login_browser_flow.spec.ts` verifies OAuth redirect,
  callback failure, cancellation, and retry behavior.

---

## See also

- [Frontend Test Map](frontend.md)
- [Frontend Unit Tests](frontend-unit.md)
- [Frontend Integration Tests](frontend-integration.md)
- [Frontend Browser E2E Tests](frontend-e2e.md)
- [Backend Authentication Test Detail](backend-authentication.md)
