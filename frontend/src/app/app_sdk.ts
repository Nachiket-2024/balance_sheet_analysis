/**
 * App-specific extension surface (see docs/mystic_auth/template-usage/overview.md).
 *
 * sdk.ts is the public surface for MysticAuth capabilities. This file only
 * bridges MysticAuth exports that sdk.ts does not currently expose, keeping
 * app pages off MysticAuth internal paths without forwarding items already
 * available from sdk.ts.
 *
 * Ships empty on purpose in every template release, so it never conflicts
 * on a `scripts/mystic_auth/upstream-sync/sync-upstream.sh` sync. If a sync ever shows an upstream
 * change here, keep YOUR version: upstream's is only ever the empty
 * starting point.
 *
 * Recheck each bridge against sdk.ts after upstream syncs. Remove a bridge
 * once MysticAuth adds that capability to the public sdk.ts surface.
 */

export { default as DashboardPage } from "../mystic_auth/dashboard/DashboardPage";

// Only bridge MysticAuth capabilities that sdk.ts does not export. Anything
// already on sdk.ts must be imported from there by app pages.
// DashboardPage is a template route component omitted from sdk.ts.
//
// These list components and types are also absent from sdk.ts; keep their
// internal MysticAuth paths centralized here until the public SDK exposes
// them. The similarly named StatTile in sdk.ts is a different component.
export { default as StatTile } from "../mystic_auth/ui/cards/StatTile";
export { default as FilterPanel } from "../mystic_auth/ui/cards/FilterPanel";
export { default as SearchInput } from "../mystic_auth/ui/filters/SearchInput";
export { default as FilterChips } from "../mystic_auth/ui/filters/FilterChips";
export type { FilterChip } from "../mystic_auth/ui/filters/FilterChips";
export type { StyledSelectOption } from "../mystic_auth/ui/filters/StyledSelect";
export type { SortState, SortDirection } from "../mystic_auth/ui/hooks/useSortState";
