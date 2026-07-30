/**
 * App-specific extension surface (see docs/mystic_auth/template-usage/overview.md).
 *
 * This is the counterpart to sdk.ts: sdk.ts re-exports the template's own
 * building blocks, this file is where a project built on this template adds
 * its own re-exports for its own domain code, kept separate so template
 * updates never conflict with app-specific additions here.
 *
 * DashboardPage: not covered by sdk.ts (it re-exports the app shell/PBAC/UI
 * primitives, but not the actual dashboard route content), so re-exported
 * here, since App.tsx renders it directly at "/dashboard" now that Companies has
 * its own permanent sidebar entry (see App.tsx's EXTRA_NAV_ITEMS) and no
 * longer needs an AppDashboardPage wrapper just to host a "View your
 * companies" button.
 */

export { default as DashboardPage } from "../mystic_auth/dashboard/DashboardPage";
