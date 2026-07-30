/**
 * Mirrors backend/app/access/permissions.py exactly: this app's own action
 * vocabulary, kept separate from mystic_auth's own PERMISSIONS constant
 * (src/mystic_auth/authorization/permissions.ts) the same way the backend
 * keeps app/access/permissions.py separate from
 * mystic_auth/authorization/permissions.py.
 */
export const APP_PERMISSIONS = {
    COMPANY_READ: "company:read",
    COMPANY_CREATE: "company:create",
    COMPANY_DELETE: "company:delete",
    BALANCE_SHEET_READ: "balance_sheet:read",
    BALANCE_SHEET_IMPORT: "balance_sheet:import",
    BALANCE_SHEET_DELETE: "balance_sheet:delete",
    LLM_CHAT: "llm:chat",
} as const;

export type AppPermissionValue = (typeof APP_PERMISSIONS)[keyof typeof APP_PERMISSIONS];
