import { createSessionUiStore } from "../store/createSessionUiStore";

interface AuditLogUiState {
    category: string | null;
    scope: string | null;
}

/** Holds the outer (category) and inner (scope) tab picks, same "null until
 * chosen" convention as accountSettingsUiStore. `scope` is shared across both
 * category branches (see AuditLogPage's own comment on why one value covers
 * both), so it's one field here too, not split per category. */
export const useAuditLogUiStore = createSessionUiStore<AuditLogUiState>({
    category: null,
    scope: null,
});
