/**
 * Public extension surface for feature code built on top of this template
 * (see docs/mystic_auth/template-usage/overview.md).
 *
 * Import from HERE, not internal paths like "../authorization/useAuthorization"
 * directly. One file to discover what's available, and one file to reconcile
 * when pulling in upstream template updates.
 *
 * Everything below is a straight re-export; see the original module for the
 * "why" behind any given piece.
 *
 * DO NOT hand-edit this file. It's a drop-in from upstream, and this is the
 * one file a `scripts/mystic_auth/upstream-sync/sync-upstream.sh` sync is expected to touch, so local
 * edits here turn a clean sync into a manual conflict. For your own
 * re-exports, use app_sdk.ts instead: it's the counterpart file upstream
 * keeps empty for exactly this purpose.
 */

// PBAC: see docs/mystic_auth/authorization/architecture/README.md
export { PERMISSIONS } from "../mystic_auth/authorization/permissions";
export type { PermissionValue } from "../mystic_auth/authorization/permissions";
export { useAuthorization } from "../mystic_auth/authorization/useAuthorization";
export { useCan, useAuthorized } from "../mystic_auth/authorization/useCan";
export { Authorized } from "../mystic_auth/authorization/Authorized";
export { IfCan } from "../mystic_auth/authorization/IfCan";
export { default as ProtectedRoute } from "../mystic_auth/authorization/ProtectedRoute";
export * as authorizationService from "../mystic_auth/authorization/authorizationService";

// App shell: the chrome every protected page renders inside. AppLayout
// takes an optional `extraNavItems` prop (NavItem, from layout/app_layout/navItems.ts)
// so your own feature routes can add sidebar links without editing
// mystic_auth/layout/app_layout/navItems.ts directly. See
// docs/mystic_auth/template-usage/frontend-customization.md#shared-chrome-extension-points.
export { default as AppLayout } from "../mystic_auth/layout/app_layout/AppLayout";
export type { NavItem } from "../mystic_auth/layout/app_layout/navItems";

// Cmd+K palette (mounted once in App.tsx, not AppLayout). Takes the same
// `extraNavItems` you give AppLayout, plus `extraSearchItems` (SearchItem)
// so your own page content, not just whole pages, shows up in palette
// search too. See docs/mystic_auth/template-usage/frontend-customization.md#shared-chrome-extension-points.
export { default as CommandPalette } from "../mystic_auth/layout/command_palette/CommandPalette";
export type { SearchItem } from "../mystic_auth/layout/command_palette/searchItems";

// Brand mark: icon badge + wordmark (falls back to /favicon.svg + APP_NAME
// unless VITE_APP_LOGO_URL is set). Use instead of hand-rolling your own
// heading/image pair on pages outside AppLayout, so a logo change updates
// everywhere.
export { default as Logo } from "../mystic_auth/layout/app_layout/Logo";

// The chrome LoginPage/SignupPage/the legal document pages render inside
// when there's no signed-in session (or the page, like Privacy/Terms,
// deliberately stays outside AppLayout even for a signed-in visitor):
// centered card, Logo, and the ThemeToggle/LanguageToggle/FontSizeControl
// cluster pinned top-right. `variant="status"` widens the card for prose
// (see LegalDocumentLayout) instead of the narrower default form width.
export { default as AuthLayout } from "../mystic_auth/layout/auth_layout/AuthLayout";

// Auth UI and mutations: reuse these if your app wraps or embeds the
// template's login/signup/reset/verification forms instead of replacing
// them wholesale. Routed page components stay out of sdk.ts so App.tsx can
// keep lazy-loading them without pulling every page into the main bundle.
export { default as LoginForm } from "../mystic_auth/auth/login/LoginForm";
export { useLoginMutation } from "../mystic_auth/auth/login/useLoginMutation";
export type { LoginRequest, LoginResponse } from "../mystic_auth/auth/login/login_types";
export { default as SignupForm } from "../mystic_auth/auth/signup/SignupForm";
export { useSignupMutation } from "../mystic_auth/auth/signup/useSignupMutation";
export type { SignupRequest, SignupResponse } from "../mystic_auth/auth/signup/signup_types";
export { default as PasswordResetRequestForm } from "../mystic_auth/auth/password_reset_request/PasswordResetRequestForm";
export { usePasswordResetRequestMutation } from "../mystic_auth/auth/password_reset_request/usePasswordResetRequestMutation";
export type {
    PasswordResetRequestPayload,
    PasswordResetRequestResponse,
} from "../mystic_auth/auth/password_reset_request/password_reset_request_types";
export { default as PasswordResetConfirmForm } from "../mystic_auth/auth/password_reset_confirm/PasswordResetConfirmForm";
export { usePasswordResetConfirmMutation } from "../mystic_auth/auth/password_reset_confirm/usePasswordResetConfirmMutation";
export type {
    PasswordResetConfirmPayload,
    PasswordResetConfirmResponse,
} from "../mystic_auth/auth/password_reset_confirm/password_reset_confirm_types";
export { default as VerifyAccountButton } from "../mystic_auth/auth/verify_account/VerifyAccountButton";
export { default as VerificationEmailRequestForm } from "../mystic_auth/auth/verify_account/VerificationEmailRequestForm";
export { useVerificationEmailRequestMutation } from "../mystic_auth/auth/verify_account/useVerificationEmailRequestMutation";
export { useVerifyAccountMutation } from "../mystic_auth/auth/verify_account/useVerifyAccountMutation";
export type {
    VerificationEmailRequestPayload,
    VerificationEmailRequestResponse,
    VerifyAccountPayload,
    VerifyAccountResponse,
} from "../mystic_auth/auth/verify_account/verify_account_types";
export { default as OAuth2LoginButton } from "../mystic_auth/auth/oauth2/OAuth2LoginButton";
export { default as OAuth2LoginButtonComponent } from "../mystic_auth/auth/oauth2/OAuth2LoginButtonComponent";
export { default as LogoutButton } from "../mystic_auth/auth/logout/LogoutButton";
export { useLogoutMutation } from "../mystic_auth/auth/logout/useLogoutMutation";
export { useLogoutAllMutation } from "../mystic_auth/auth/logout_all/useLogoutAllMutation";
export type { LogoutResponse } from "../mystic_auth/auth/logout/logout_types";
export type { CurrentUserProfile } from "../mystic_auth/auth/current_user/current_user_types";
export { useCurrentUserQuery } from "../mystic_auth/auth/current_user/useCurrentUserQuery";

// Password validation UI mirrors the backend password service. Reuse these
// when app-owned flows collect passwords.
export { checkPasswordRules, evaluatePasswordStrength, validatePassword } from "../mystic_auth/auth/password_rules/passwordRules";
export type { PasswordRules } from "../mystic_auth/auth/password_rules/passwordRules";
export { default as PasswordRulesChecklist } from "../mystic_auth/auth/password_rules/PasswordRulesChecklist";
export { default as PasswordStrengthPanel } from "../mystic_auth/auth/password_rules/PasswordStrengthPanel";

// Theme/language/font-size controls: the same pinned top-right toggles
// AuthLayout gives login/signup, for pages outside the auth shell that want
// the same "adjust before you sign in" affordance.
export { default as ThemeToggle } from "../mystic_auth/layout/controls/ThemeToggle";
export { default as LanguageToggle } from "../mystic_auth/layout/controls/LanguageToggle";
export { default as FontSizeControl } from "../mystic_auth/layout/controls/FontSizeControl";
// All three above, pre-grouped into one bordered/rounded segmented control:
// the same trio AuthLayout/Navbar render together, in the same order.
export { default as ControlCluster } from "../mystic_auth/layout/controls/ControlCluster";

// Underline/darken hover link, the same treatment LoginPage/SignupForm give
// their own Privacy Policy/Terms of Service footnote links.
export { default as AuthInlineLink } from "../mystic_auth/ui/links/AuthInlineLink";

// The shared i18next instance itself (not just useTranslation, which you can
// already import from "react-i18next" - see LoginPage.tsx). Your own
// feature folder doesn't belong in mystic_auth/translations/'s NAMESPACES
// list (upstream's own namespace-per-template-feature contract), so
// register your own namespace at runtime instead:
// translations.addResourceBundle("en", "yourNamespace", enJson), once per
// language, then useTranslation("yourNamespace") as normal. See
// app/translations/ plus mystic_auth/translations/languages/ for the worked
// app-owned locale layout.
export { default as translations } from "../mystic_auth/translations/translations";

// Route-splitting: use in place of React.lazy for your own routed pages so
// they drive the same shared RouteProgressBar this template's routes do
// (see App.tsx). Plain React.lazy still works, it just won't show loading
// progress for that route.
export { trackedLazy } from "../mystic_auth/ui/routing/trackedLazy";

// Mount once at your app root (see App.tsx) so any component/thunk can call
// toaster.create({...})
export { Toaster } from "../mystic_auth/ui/toaster/toaster";
export { toaster } from "../mystic_auth/ui/toaster/toasterInstance";

// Generic UI primitives: no identity/PBAC coupling, reused as-is by your
// own feature pages the same way this template's own pages do.
// Button: the app's standard button component. Use its
// `variant` prop ("brand", "brand-outline", "destructive",
// "destructive-outline", "brand-tinted-outline", "secondary", "icon",
// "brand-subtle", "outline", "ghost", "link") instead of spreading a
// hover-fix props object - see frontend/src/mystic_auth/ui/buttons/Button.tsx for what each variant looks
// like and why.
export { Button, type ButtonProps } from "../mystic_auth/ui/buttons/Button";
export { buttonVariants } from "../mystic_auth/ui/buttons/button-variants";
export { default as LoadingState } from "../mystic_auth/ui/feedback/LoadingState";
export { default as Card } from "../mystic_auth/ui/cards/Card";
export { default as PageContainer } from "../mystic_auth/ui/navigation/PageContainer";
export { default as DataTable } from "../mystic_auth/ui/DataTable/DataTable";
export type { DataTableColumn } from "../mystic_auth/ui/DataTable/DataTable";
export { default as ConfirmDialog } from "../mystic_auth/ui/feedback/ConfirmDialog";
export { default as FormAlert } from "../mystic_auth/ui/feedback/FormAlert";
export { default as Badge } from "../mystic_auth/ui/badges/Badge";
export { default as Breadcrumbs } from "../mystic_auth/ui/navigation/Breadcrumbs";
export { default as Pagination } from "../mystic_auth/ui/navigation/Pagination";
export { default as PasswordInput } from "../mystic_auth/ui/inputs/PasswordInput";
export { default as StatTile } from "../mystic_auth/ui/display/StatTile";
export { default as StyledSelect } from "../mystic_auth/ui/filters/StyledSelect";
export { Input, type InputProps } from "../mystic_auth/ui/inputs/Input";
export { inputVariants } from "../mystic_auth/ui/inputs/input-variants";
export { Textarea } from "../mystic_auth/ui/inputs/Textarea";
export { SEARCH_QUERY_MAX_LENGTH } from "../mystic_auth/ui/styles/inputStyles";
export { default as TableActionButton } from "../mystic_auth/ui/table_actions/TableActionButton";
export { default as TableActionIconButton } from "../mystic_auth/ui/table_actions/TableActionIconButton";
export { TABLE_ACTION_PALETTE_STYLES } from "../mystic_auth/ui/table_actions/tableActionPalettes";
export { useCooldown } from "../mystic_auth/ui/hooks/useCooldown";
export { useDebouncedValue } from "../mystic_auth/ui/hooks/useDebouncedValue";
export { usePageResetOn } from "../mystic_auth/ui/hooks/usePageResetOn";
export { useScrollToHash } from "../mystic_auth/ui/hooks/useScrollToHash";
export { useSortState } from "../mystic_auth/ui/hooks/useSortState";
export { default as ErrorBoundary } from "../mystic_auth/ui/routing/ErrorBoundary";
export { default as RouteFadeIn } from "../mystic_auth/ui/routing/RouteFadeIn";
export { default as RouteProgressBar } from "../mystic_auth/ui/routing/RouteProgressBar";
export { default as RouteSkeleton } from "../mystic_auth/ui/routing/RouteSkeleton";

// API layer: see docs/mystic_auth/architecture/frontend.md#api-layer
export { default as api } from "../mystic_auth/api/axiosInstance";
export { extractApiErrorMessage, isForbiddenError, translateErrorCode } from "../mystic_auth/api/apiError";
export * as authApi from "../mystic_auth/api/auth_api";
export * as accountSettingsApi from "../mystic_auth/api/account_settings_api";
export * as auditApi from "../mystic_auth/api/audit_api";
export * as bulkAssignmentApi from "../mystic_auth/api/bulk_assignment_api";
export * as permissionsApi from "../mystic_auth/api/permissions_api";
export * as policiesApi from "../mystic_auth/api/policies_api";
export * as rateLimitsApi from "../mystic_auth/api/rate_limits_api";
export * as usersApi from "../mystic_auth/api/users_api";

// Session/client state
export { useAuthStore } from "../mystic_auth/store/authStore";
export { queryClient } from "../mystic_auth/core/queryClient";

// Settings: add your own VITE_* fields to frontend/.env.example and
// core/settings.ts, read them from here rather than import.meta.env
// directly at every call site
export { default as settings, APP_NAME, SUPPORT_EMAIL } from "../mystic_auth/core/settings";

// Error monitoring: reports a caught-but-still-noteworthy error the same
// way an uncaught render error gets reported automatically (see
// ui/routing/ErrorBoundary.tsx). Safe no-op when VITE_SENTRY_DSN is unset, see
// docs/mystic_auth/error-monitoring/overview.md
export { reportError } from "../mystic_auth/core/errorMonitoring";
