import { createSessionUiStore } from "../store/createSessionUiStore";
import { ALL_VALUE } from "./PoliciesFilterBar";

interface PoliciesUiState {
    search: string;
    resourceType: string;
    status: string;
    containsAction: string;
    destructiveOnly: boolean;
}

export const usePoliciesUiStore = createSessionUiStore<PoliciesUiState>({
    search: "",
    resourceType: ALL_VALUE,
    status: ALL_VALUE,
    containsAction: ALL_VALUE,
    destructiveOnly: false,
});
