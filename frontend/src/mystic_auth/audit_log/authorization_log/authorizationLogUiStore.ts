import { createSessionUiStore } from "../../store/createSessionUiStore";
import { ALL_VALUE, DEFAULT_TIME_RANGE_STATE, type TimeRangeState } from "../auditLogListConfig";

interface AuthorizationLogFilterState extends TimeRangeState {
    search: string;
    action: string;
    resourceType: string;
    allowed: string;
    sortKey: string;
    sortDir: "asc" | "desc";
}

const defaults: AuthorizationLogFilterState = {
    search: "",
    action: ALL_VALUE,
    resourceType: ALL_VALUE,
    allowed: ALL_VALUE,
    sortKey: "created_at",
    sortDir: "desc",
    ...DEFAULT_TIME_RANGE_STATE,
};

// See securityLogUiStore.ts's matching comment: separate stores per sub-tab,
// since each fully unmounts when the other is active.
export const useAllAuthorizationLogUiStore = createSessionUiStore<AuthorizationLogFilterState>({ ...defaults });

const { search: _search, ...myDefaults } = defaults;
export const useMyAuthorizationLogUiStore = createSessionUiStore<Omit<AuthorizationLogFilterState, "search">>({
    ...myDefaults,
});
