/**
 * App-specific extension surface (see docs/mystic_auth/template-usage/overview.md).
 *
 * This is the counterpart to sdk.ts: sdk.ts re-exports the template's own
 * building blocks, this file is where a project built on this template adds
 * its own re-exports for its own domain code, kept separate so template
 * updates never conflict with app-specific additions here.
 *
 * DashboardPage is not covered by sdk.ts, which only exports app shell, PBAC,
 * and UI primitives. App.tsx renders it directly at "/dashboard".
 */

export { default as DashboardPage } from "../mystic_auth/dashboard/DashboardPage";

// App buttons reuse mystic_auth hover fixes without each page importing
// internal UI paths directly.
export { default as TableActionButton } from "../mystic_auth/ui/TableActionButton";
export { BRAND_SOLID_HOVER_PROPS, BRAND_OUTLINE_HOVER_PROPS } from "../mystic_auth/ui/styles/buttonStyles";

// Table controls reused by CompaniesPage to match mystic_auth list pages.
export { default as StatTile } from "../mystic_auth/ui/StatTile";
export { default as StyledSelect } from "../mystic_auth/ui/StyledSelect";
export type { StyledSelectOption } from "../mystic_auth/ui/StyledSelect";
export { SEARCH_INPUT_PROPS } from "../mystic_auth/ui/styles/inputStyles";
export { useSortState } from "../mystic_auth/ui/hooks/useSortState";
export type { SortState, SortDirection } from "../mystic_auth/ui/hooks/useSortState";
export { useDebouncedValue } from "../mystic_auth/ui/hooks/useDebouncedValue";
export { default as Pagination } from "../mystic_auth/ui/Pagination";
export { usePageResetOn } from "../mystic_auth/ui/hooks/usePageResetOn";
