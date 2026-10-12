# Frontend Unit Tests
---

*New to a term here? See the [Testing Glossary](../glossary/testing.md).*

These 102 MysticAuth Vitest modules, plus three app-wrapper modules, isolate one frontend rule, API client, hook, store,
component, or helper. They are intentionally narrower than page integration
tests. A passing unit test means the named client-side contract works with
controlled inputs; it does not mean that the backend accepted a request.

---

## Account settings and active sessions

- `account_settings/useUnsavedChangesWarning.test.tsx` verifies dirty-form
  detection, navigation blocking, and confirmation behavior.
- `active_sessions/parseUserAgent.test.ts` verifies browser/device parsing for
  the session list, including unknown and incomplete user agents.

## Shared UI, stores, and security-log presentation

- `store/fontSizeStore.test.ts` verifies persisted font-size selection and
  clamping at the supported boundaries.
- `ui/shared_components.test.tsx` verifies the public behavior of shared
  badges, buttons, cards, inputs, links, loading states, stat tiles,
  collapsible sections, breadcrumbs, and page slots.
- `ui/shadcn/` covers the shared shadcn/Radix primitives used by the feature
  pages.
- `audit_log/security_log/securityAccessChangeDetails.test.ts` verifies
  access-change detail rendering for complete, partial, blank, and unknown
  event metadata.

## API clients

- `api/account_settings_api.test.ts` verifies account-settings URLs, methods,
  bodies, and typed errors.
- `api/apiError.test.ts` verifies conversion of HTTP and unknown failures into
  the frontend API-error shape.
- `api/audit_api.test.ts` verifies audit and security-log query parameters,
  response mapping, and errors.
- `api/getCurrentUserApi.test.ts` verifies the current-user request and typed
  response handling.
- `api/loginApi.test.ts` verifies login request payloads and error mapping.
- `api/logoutApi.test.ts` verifies logout and logout-all requests.
- `api/oauth2Api.test.ts` verifies OAuth provider and callback request URLs.
- `api/passwordResetApi.test.ts` verifies reset-request and reset-confirmation
  payloads and failures.
- `api/policies_api.test.ts` verifies policy list, CRUD, status, and assignment
  request construction.
- `api/rate_limits_api.test.ts` verifies rate-limit query and reset requests.
- `api/signupApi.test.ts` verifies signup payloads and validation errors.
- `api/users_api.test.ts` verifies user list, detail, update, grant, bulk, and
  export request construction.
- `api/verifyAccountApi.test.ts` verifies verification request and token
  confirmation calls.

## Audit log presentation

- `audit_log/auditLogListConfig.test.ts` verifies category-specific columns,
  labels, filters, and display configuration.
- `audit_log/auditLogQueries.test.tsx` verifies query-key construction,
  pagination/filter state, and enabled/disabled query behavior.
- `audit_log/authorization_log/AuthorizationDetailsDrawer.test.tsx` verifies
  authorization decision details and safe metadata display.
- `audit_log/authorization_log/AuthorizationFilterBar.test.tsx` verifies
  authorization filters, reset behavior, and controlled values.
- `audit_log/authorization_log/authorizationLogColumns.test.tsx` verifies
  authorization actor, action, resource, outcome, and timestamp columns.
- `audit_log/security_log/LoginTrendChart.test.tsx` verifies login-trend
  totals, empty and loading states, chart/table modes, failed-only scaling,
  keyboard tooltips, long-range label thinning, and background refresh feedback.
- `audit_log/security_log/SecurityDetailsDrawer.test.tsx` verifies security
  event details and safe rendering of event metadata.
- `audit_log/security_log/SecurityFilterBar.test.tsx` verifies security-event
  filters and reset behavior.
- `audit_log/security_log/securityLogColumns.test.tsx` verifies security event
  columns, labels, and redaction-safe values.

## Authentication and session lifecycle

- `auth/auth_page_mobile_overflow.test.tsx` verifies auth layouts do not
  produce horizontal overflow at narrow widths.
- `auth/current_user/useCurrentUserQuery.test.tsx` verifies current-user query
  loading, success, error, and cache state.
- `auth/oauth2/OAuth2LoginButton.test.tsx` verifies provider selection,
  disabled/pending behavior, and redirect initiation.
- `auth/password_reset_confirm_form.test.tsx` verifies reset form validation,
  submit state, success, and error feedback.
- `auth/password_reset_request_form.test.tsx` verifies reset-request
  validation, non-disclosing success, and cooldown behavior.
- `auth/password_rules/PasswordRulesChecklist.test.tsx` verifies individual
  password-rule indicators and accessible status text.
- `auth/password_rules/PasswordStrengthPanel.test.tsx` verifies strength
  calculation presentation and guidance for each strength level.
- `auth/password_rules/passwordRules.test.ts` verifies the pure password
  policy predicates and boundary values.
- `auth/session_lifecycle/crossTabRefresh.test.ts` verifies cross-tab token
  refresh coordination and duplicate-request prevention.
- `auth/session_lifecycle/setupAuthInterceptor.test.tsx` verifies 401 refresh,
  retry, logout, and failure handling in the HTTP interceptor.
- `auth/session_lifecycle/useSessionEventsStream.test.tsx` verifies SSE session
  events update auth state and close/reconnect safely.
- `auth/signup_form_legal_consent.test.tsx` verifies required legal consent
  and the signup button's enabled state.
- `auth/verify_account/verification_email_request_form.test.tsx` verifies
  verification-email form validation, pending, success, and errors.
- `auth/verify_account/verify_account_button.test.tsx` verifies token
  verification action states and navigation.

## Authorization and policy helpers

- `authorization/Authorized.test.tsx` verifies permission-based rendering and
  the fail-closed result while permissions are unknown.
- `authorization/ProtectedRoute.test.tsx` verifies route redirects for
  unauthenticated, unauthorized, and authorized users.
- `authorization/authorizationService.test.ts` verifies client permission
  lookup and normalized authorization decisions.
- `authorization/destructiveActions.test.ts` verifies destructive-action
  visibility and confirmation requirements.
- `authorization/grantability.test.ts` verifies which permissions/policies a
  caller may grant based on effective authority.
- `authorization/useAuthorization.test.tsx` verifies hook loading, decisions,
  and decision refresh behavior.
- `authorization/useCan.test.tsx` verifies the small permission-check hook.
- `policies/effectiveGrants.test.ts` verifies merging of roles, policies, and
  direct grants into effective permission sets.
- `policies/policyCardHelpers.test.ts` verifies policy-card labels, actions,
  status, and permission-derived controls.
- `policies/policyListHelpers.test.ts` verifies policy filtering, sorting, and
  display helpers.
- `policies/selfPermissionMutationGuardArming.test.tsx` verifies the client
  guard that warns before removing the current user's protective access.

## Application shell, stores, theme, and translations

- `core/errorMonitoring.test.ts` verifies frontend error-monitoring setup and
  safe reporting behavior.
- `layout/app_layout/AppLayout.test.tsx` verifies shell composition, mobile
  navigation dismissal, downstream navbar actions, and command-palette wiring.
- `layout/app_layout/Logo.test.tsx` verifies logo rendering and accessible
  branding link behavior.
- `layout/app_layout/Navbar.test.tsx` verifies navbar controls and responsive
  menu behavior.
- `layout/app_layout/Sidebar.test.tsx` verifies navigation items and active
  route state.
- `layout/app_layout/routePrefetch.test.ts` verifies route-prefetch decisions
  and duplicate-load avoidance.
- `layout/command_palette/CommandPalette.test.tsx` verifies search, keyboard
  navigation, command execution, and dismissal.
- `layout/controls/LanguageToggle.test.tsx` verifies language selection and
  accessible control state.
- `store/createSessionUiStore.test.ts` verifies session UI state transitions.
- `store/languageStore.test.ts` verifies language persistence and updates.
- `store/networkStatusStore.test.ts` verifies online/offline transitions.
- `store/routeLoadingStore.test.ts` verifies route-progress state.
- `store/themeStore.test.ts` verifies theme selection and persistence.
- `theme/appearanceThemeOverrides.test.ts` verifies appearance override
  resolution.
- `theme/applyFaviconAndMetaColor.test.ts` verifies favicon and meta-color DOM
  updates for the selected theme.
- `theme/brandIcon.test.ts` verifies brand icon variants and accessibility.
- `theme/fgTokens.test.ts` verifies foreground token generation.
- `theme/generateBrandScale.test.ts` verifies generated brand color scales.
- `translations/translation_key_parity.test.ts` verifies every locale has the
  same translation-key set as the source locale.

Status-page tests read the configured frontend `APP_NAME` rather than asserting
the template's default `MysticAuth` label. They accept either the configured
wordmark text or the accessible custom-logo image, so downstream branding and
`VITE_APP_LOGO_URL` remain valid test configurations.

## Rate limits and shared UI

- `rate_limits/RateLimitsFilterBar.test.tsx` verifies filter controls, values,
  reset, and accessibility labels.
- `rate_limits/RateLimitsStatsCard.test.tsx` verifies statistics formatting,
  loading, empty, and error presentation.
- `ui/AppTooltip.test.tsx` verifies tooltip trigger, content, delay, and
  keyboard behavior.
- `ui/Breadcrumbs.test.tsx` verifies breadcrumb labels, links, and current-page
  semantics.
- `ui/ConfirmDialog.test.tsx` verifies confirmation, cancel, pending, and
  destructive dialog behavior.
- `ui/CopyLinkButton.test.tsx` verifies clipboard success, failure, and status
  feedback.
- `ui/DataTable/DataTable.test.tsx` verifies table rendering, loading, empty,
  sorting, and row interaction.
- `ui/DataTable/DataTableSelection.test.tsx` verifies row selection, select
  all, indeterminate state, and disabled rows.
- `ui/DetailsDrawer.test.tsx` verifies drawer open/close, focus, and details
  layout.
- `ui/FilterChips.test.tsx` verifies applied-filter display and removal.
- `ui/FormAlert.test.tsx` verifies accessible error and warning presentation.
- `ui/GroupedSearchSelect.test.tsx` verifies grouped options, search, and
  keyboard selection.
- `ui/LoadingState.test.tsx` verifies loading indicators and accessible status.
- `ui/SegmentedControl.test.tsx` verifies selection, keyboard navigation, and
  disabled options.
- `ui/StyledSelect.test.tsx` verifies select rendering, values, and errors.
- `ui/TimeRangeControl.test.tsx` verifies range selection and validation.
- `ui/dateFormatters.test.ts` verifies timezone-safe date and relative-time
  formatting.
- `ui/network/OfflineBanner.test.tsx` verifies offline/online banner state.
- `ui/routing/ErrorBoundary.test.tsx` verifies caught-render-error fallback
  and recovery action.
- `ui/routing/RouteProgressBar.test.tsx` verifies route-transition progress.
- `ui/routing/trackedLazy.test.tsx` verifies lazy-route tracking and loading.
- `ui/security_controls.test.tsx` verifies security-sensitive UI helpers and
  safe default control states.
- `ui/sortState.test.ts` verifies sort parsing, toggling, and serialization.
- `ui/toaster/toaster.test.tsx` verifies toast creation, dismissal, and timing.
- `ui/useCooldown.test.tsx` verifies cooldown countdown and reset behavior.
- `ui/useScrollToHash.test.tsx` verifies hash navigation and scroll timing.
- `users/useUserAccessDialogState.test.tsx` verifies access-dialog selection,
  tab state, and reset behavior.
- `users/userQueries.test.ts` verifies user-query keys, pagination, and cache
  invalidation behavior.

---

## See also

- [Frontend Test Map](frontend.md)
- [Frontend Integration Tests](frontend-integration.md)
- [Frontend Browser E2E Tests](frontend-e2e.md)
- [Frontend Test Map](frontend.md)
- [Testing Overview](overview.md)
