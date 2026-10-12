import { createSessionUiStore } from "../store/createSessionUiStore";
import { ALL_VALUE } from "./UsersFilterBar";

interface UsersUiState {
    role: string;
    verified: string;
    status: string;
    policy: string;
    permission: string;
    lastLogin: string;
    sortKey: string;
    sortDir: "asc" | "desc";
}

/** `search` is deliberately excluded: it already has its own one-shot URL
 * deep link (`?search=`, see useUsersPageState's matching comment), and
 * unlike the other filters isn't itself something worth re-applying to a
 * different investigation next visit. Row selection is excluded too - it's
 * transactional (tied to specific rows currently on screen), not a
 * preference, so it stays plain useState in useUsersPageState. */
export const useUsersUiStore = createSessionUiStore<UsersUiState>({
    role: ALL_VALUE,
    verified: ALL_VALUE,
    status: ALL_VALUE,
    policy: ALL_VALUE,
    permission: ALL_VALUE,
    lastLogin: ALL_VALUE,
    sortKey: "",
    sortDir: "desc",
});
