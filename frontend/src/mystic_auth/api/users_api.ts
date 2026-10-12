import api from "./axiosInstance";

export interface ManagedUserRead {
    id: number;
    name: string;
    email: string;
    role: string | null;
    is_verified: boolean;
    is_active: boolean;
    created_at: string;
    updated_at: string;
    deleted_at: string | null;
    /** Set on every successful sign-in. null means this account has never
     * signed in (e.g. created by a permission holder but not yet used). */
    last_login_at: string | null;
    has_password: boolean;
    /** Per-user brand color override (#rrggbb). null = using the app
     * default scale (app/theme.ts). See appearanceStore.ts. */
    brand_color: string | null;
    /** Self-service PUT /users/me only, and only set on a password change: whether the
     * account's other sessions got revoked. False means the password changed but Valkey
     * was unreachable, so other sessions are still live - see ChangePasswordCard.tsx. */
    sessions_revoked?: boolean | null;
}

export interface UserUpdatePayload {
    name?: string;
    password?: string;
    // Required when changing a password on an account that already has one
    // (self-service PUT /users/me only; ignored by the management route).
    // Not needed when setting a password for the first time on an OAuth-only account.
    current_password?: string;
    /** #rrggbb to set a custom brand color, or null to reset to the app
     * default. Omitted (undefined) leaves the stored value unchanged. */
    brand_color?: string | null;
}

export interface UserStatsRead {
    total: number;
    verified: number;
    unverified: number;
    inactive: number;
}

export interface ListUsersParams {
    limit?: number;
    offset?: number;
    search?: string;
    /** Exact match, one of ManagedUserRead['role']'s real values. */
    role?: string;
    isVerified?: boolean;
    /** One of "active" | "inactive" | "deleted" (see UsersPage.tsx's Status badge). */
    status?: string;
    /** Exact match on the name of an assigned policy (see PolicyRead['name']). */
    policy?: string;
    /** Users holding a policy whose actions include this permission, one of
     * PERMISSIONS' own values (authorization/permissions.ts). */
    permission?: string;
    permissionSource?: "policy" | "direct";
    /** Column to sort by. Must be one of the backend's allowlisted sortable columns
     * (see user_base_crud.py's _SORTABLE_COLUMN_NAMES); anything else is ignored
     * server-side and falls back to id. */
    sortBy?: string;
    sortDir?: "asc" | "desc";
    /** Relative bucket, one of "today" | "7d" | "30d" | "90d" | "never".
     * Ignored server-side if lastLoginFrom/lastLoginTo are set. */
    lastLogin?: string;
    /** Custom range bounds (ISO datetime strings), inclusive. Either one
     * alone is enough to filter, same as most date-range pickers. */
    lastLoginFrom?: string;
    lastLoginTo?: string;
}

function toApiParams({
    limit = 1000, offset = 0, search, role, isVerified, status, policy, permission, permissionSource, sortBy, sortDir,
    lastLogin, lastLoginFrom, lastLoginTo,
}: ListUsersParams) {
    return {
        limit, offset, search, role, is_verified: isVerified, status, policy, permission,
        permission_source: permissionSource,
        sort_by: sortBy, sort_dir: sortDir,
        last_login: lastLogin, last_login_from: lastLoginFrom, last_login_to: lastLoginTo,
    };
}

// Total matching row count rides the X-Total-Count response header; UsersPage reads
// it for the page count (see userQueries.ts).
export const listUsersApi = (params: ListUsersParams = {}) =>
    api.get<ManagedUserRead[]>("/users/", { params: toApiParams(params) });

// Aggregate counts (total/verified/unverified/inactive) across the whole
// table, independent of the main list's current page/filters.
export const getUserStatsApi = () =>
    api.get<UserStatsRead>("/users/stats");

export const updateUserApi = (userEmail: string, payload: UserUpdatePayload) =>
    api.put<ManagedUserRead>(`/users/${encodeURIComponent(userEmail)}`, payload);

// Soft delete (default, reversible): sets is_active=false + deleted_at,
// revokes active sessions, preserves the row and its audit history.
export const deleteUserApi = (userEmail: string) => api.delete(`/users/${encodeURIComponent(userEmail)}`);

// Hard delete (separate, irreversible operation): requires users:delete_any,
// a distinct and more sensitive permission from users:deactivate_any.
export const purgeUserApi = (userEmail: string) => api.delete(`/users/${encodeURIComponent(userEmail)}/purge`);

// Undo a soft delete, requires users:reactivate.
export const reactivateUserApi = (userEmail: string) =>
    api.patch<ManagedUserRead>(`/users/${encodeURIComponent(userEmail)}/reactivate`);

export const updateUserRoleApi = (userEmail: string, role: string) =>
    api.patch(`/users/${encodeURIComponent(userEmail)}/role`, { role });

// CSV of every user matching the given filters (no limit/offset - always
// the whole filtered set, unlike listUsersApi's paginated page). Same
// filter params as the list, blob response so UsersPage can turn it into
// a real file download.
export const exportUsersApi = (params: ListUsersParams = {}) =>
    api.get<Blob>("/users/export", { params: toApiParams(params), responseType: "blob" });
