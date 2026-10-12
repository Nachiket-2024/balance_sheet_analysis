# Frontend Page Test Detail
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

This page explains the page-level frontend suites beyond the authorization
specific cases. Integration tests use controlled API responses to cover every
render state. Browser tests add actual navigation, focus, keyboard, overflow,
and accessibility behavior.

---

## Account settings and dashboard

- `integration/account_settings/account_settings_page.test.tsx` covers tab
  navigation, profile/password/appearance data, save/loading/error states,
  and permission-sensitive controls.
- `integration/account_settings/account_settings_tab_persistence.test.tsx`
  covers selected-tab persistence through navigation/reload.
- `integration/account_settings/appearance_card.test.tsx` covers theme choice,
  persistence, and feedback.
- `integration/account_settings/delete_account_card.test.tsx` covers
  destructive confirmation requirements and failure handling.
- `integration/account_settings/confirm_delete_account_page.test.tsx` covers
  valid, missing, expired, and invalid confirmation tokens.
- `integration/dashboard/dashboard_page.test.tsx` covers loading/error/data
  states, statistics, identity, quick actions, and session controls.
- `e2e/account_settings/account_settings_page_browser.spec.ts` covers these
  settings interactions in a real browser with mocked API responses.
- `e2e/account_settings/confirm_delete_account_browser_flow.spec.ts` covers
  token-page navigation and invalid-token redirects.
- `e2e/dashboard/dashboard_page_browser.spec.ts` covers responsive dashboard
  rendering, controls, and least-privilege redirects.
- `e2e/dashboard/active_sessions_browser.spec.ts` covers session-card revoke,
  confirmation, and focus restoration.

## Users and access dialogs

- `integration/users/users_page.test.tsx` covers list data, pagination,
  filters, row actions, and page-level access.
- `users_page_list_controls.test.tsx` covers search, filters, sorting,
  pagination, and empty state independently from row actions.
- `users_page_stats_card.test.tsx` covers statistics loading, error, and
  responsive presentation.
- `users_page_access_dialog_details.test.tsx` covers selected-user identity
  and effective access details.
- `users_page_access_dialog_permissions.test.tsx` covers direct permission
  grant/revoke UI, request states, and refresh.
- `users_page_access_dialog_policies.test.tsx` covers policy assignment and
  effective-policy display.
- `users_page_access_dialog_policy_actions.test.tsx` covers action-level policy
  mutation and follow-up state.
- `users_page_access_dialog_self_protection.test.tsx` covers protection against
  removing the current caller's own required access.
- `users_page_bulk_actions.test.tsx` covers selection, confirmation, success,
  partial failure, and list refresh.
- `users_page_bulk_permission_actions.test.tsx` covers bulk direct grants and
  per-item result handling.
- `users_page_bulk_policy_actions.test.tsx` covers bulk policy assignment,
  removal, and per-item results.
- `e2e/users/users_page_browser.spec.ts` covers visible user tables, dialogs,
  escaped content, and permission gates in a real browser.

## Policies, permissions, audit log, and rate limits

- `integration/policies/policies_page_list_and_form.test.tsx` covers list,
  create/edit form, validation, and mutation feedback.
- `policies_page_list_controls.test.tsx` covers search, filters, sorting,
  pagination, and empty results.
- `policies_page_status_and_delete.test.tsx` covers status mutation, protected
  policy guards, delete confirmation, and errors.
- `policies_page_follow_up_dialog.test.tsx` covers post-mutation follow-up
  dialog actions and API result states.
- `policies_page_follow_up_guards.test.tsx` covers hiding/disabling follow-up
  actions when the effective grant is insufficient.
- `integration/permissions/permissions_page_details_and_errors.test.tsx`
  covers permission details and missing/error data.
- `permissions_page_filters.test.tsx` covers search, category filters, and
  empty results.
- `permissions_page_groups.test.tsx` covers grouping and expansion.
- `integration/audit_log/audit_log_page.test.tsx` covers category, scope,
  filters, pagination, details, loading, empty, and errors.
- `audit_log_tab_and_filter_persistence.test.tsx` covers tab/filter state
  persistence across supported navigation.
- `integration/rate_limits/rate_limits_page.test.tsx` covers data, filters,
  reset confirmation, loading/error, and permission gates.
- `e2e/policies/policies_page_browser.spec.ts`,
  `e2e/permissions/permissions_page_browser.spec.ts`,
  `e2e/audit_log/audit_log_page_browser.spec.ts`, and
  `e2e/rate_limits/rate_limits_page_browser.spec.ts` repeat the critical route,
  control, filter, and gate behavior in a real browser.

---

## What is mocked versus real

Vitest integration files mock API responses so each loading, error, empty,
permission, and success branch is deterministic. Ordinary Playwright page
specs also mock APIs so layout and interaction regressions do not depend on
database state. The real disposable-account login test and the real seeded
permission matrix are the exceptions. The matrix is documented in [Frontend
Authorization Test Detail](frontend-authorization.md).

---

## See also

- [Frontend Test Map](frontend.md)
- [Frontend Integration Tests](frontend-integration.md)
- [Frontend Browser E2E Tests](frontend-e2e.md)
- [Frontend Authorization Test Detail](frontend-authorization.md)
