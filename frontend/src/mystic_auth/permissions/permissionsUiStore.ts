import { createSessionUiStore } from "../store/createSessionUiStore";
import { ALL_VALUE, type PermissionQuickFilter } from "./PermissionsFilterBar";

interface PermissionsUiState {
    search: string;
    resourceType: string;
    quickFilter: PermissionQuickFilter;
    /** Manually-opened resource-type groups. Stored as an array (Sets don't
     * survive structural sharing/serialization as cleanly and every consumer
     * here just needs `.has`/iteration), rebuilt into a Set where used. */
    expandedTypes: string[];
}

export const usePermissionsUiStore = createSessionUiStore<PermissionsUiState>({
    search: "",
    resourceType: ALL_VALUE,
    quickFilter: "all",
    expandedTypes: [],
});
