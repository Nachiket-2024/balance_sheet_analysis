import { createSessionUiStore } from "../store/createSessionUiStore";
import { ALL_VALUE } from "./RateLimitsFilterBar";
import type { SortState } from "../ui/hooks/useSortState";

interface RateLimitsUiState {
    endpoint: string;
    identifier: string;
    scope: string;
    sort: SortState;
    kind: "all" | "at_limit" | "login_lockouts";
}

export const useRateLimitsUiStore = createSessionUiStore<RateLimitsUiState>({
    endpoint: "",
    identifier: "",
    scope: ALL_VALUE,
    sort: { key: "endpoint", direction: "asc" },
    kind: "all",
});
