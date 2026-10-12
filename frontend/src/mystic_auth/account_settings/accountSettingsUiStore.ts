import { createSessionUiStore } from "../store/createSessionUiStore";

interface AccountSettingsUiState {
    /** null until a tab is actually picked (either by URL deep link or a click),
     * so a fresh session still falls through to AccountSettingsPage's own "profile"
     * default instead of this store racing it with a stale value. */
    activeTab: string | null;
}

export const useAccountSettingsUiStore = createSessionUiStore<AccountSettingsUiState>({
    activeTab: null,
});
