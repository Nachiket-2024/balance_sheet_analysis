import { createSessionUiStore } from "../../store/createSessionUiStore";
import { ALL_VALUE, DEFAULT_TIME_RANGE_STATE, type TimeRangeState } from "../auditLogListConfig";

interface SecurityLogFilterState extends TimeRangeState {
    search: string;
    eventType: string;
    ipAddress: string;
    success: string;
    sortKey: string;
    sortDir: "asc" | "desc";
}

const defaults: SecurityLogFilterState = {
    search: "",
    eventType: ALL_VALUE,
    ipAddress: ALL_VALUE,
    success: ALL_VALUE,
    sortKey: "created_at",
    sortDir: "desc",
    ...DEFAULT_TIME_RANGE_STATE,
};

/** Separate stores (not one store with "all"/"mine" slices): AllSecurityLogSection and
 * MySecurityLogSection are independent sub-tabs that fully unmount on switch (AuditLogPage's
 * TabsContent has no forceMount), so each needs its own filter memory, not a shared shape
 * where "all" has a `search` field "mine" doesn't. */
export const useAllSecurityLogUiStore = createSessionUiStore<SecurityLogFilterState>({ ...defaults });

// No `search` field: MySecurityLogSection has no search box (already scoped to one user).
const { search: _search, ...myDefaults } = defaults;
export const useMySecurityLogUiStore = createSessionUiStore<Omit<SecurityLogFilterState, "search">>({
    ...myDefaults,
});
