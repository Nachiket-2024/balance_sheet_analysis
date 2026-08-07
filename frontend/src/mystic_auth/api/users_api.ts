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
    has_password: boolean;
}

export interface UserUpdatePayload {
    name?: string;
    password?: string;
    // Required by the backend when changing the password on an account that
    // already has one (self-service PUT /users/me only; the management route
    // ignores it). Not needed when setting a password for the first time on
    // an OAuth-only account.
    current_password?: string;
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
    /** Column to sort by; must be one of the backend's own allowlisted
     * sortable columns (see user_base_crud.py's _SORTABLE_COLUMN_NAMES) -
     * any other value is ignored server-side and falls back to id. */
    sortBy?: string;
    sortDir?: "asc" | "desc";
}

function toApiParams({
    limit = 1000, offset = 0, search, role, isVerified, status, sortBy, sortDir,
}: ListUsersParams) {
    return {
        limit, offset, search, role, is_verified: isVerified, status, sort_by: sortBy, sort_dir: sortDir,
    };
}

// X-Total-Count (total matching rows, ignoring limit/offset) rides the
// response headers rather than the body: response_model on the backend
// stays a plain list, and the header is what UsersPage derives its page
// count from (see userQueries.ts).
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

// Hard delete (separate, irreversible operation): requires users:purge,
// a distinct and more sensitive permission from users:delete_any.
export const purgeUserApi = (userEmail: string) => api.delete(`/users/${encodeURIComponent(userEmail)}/purge`);

// Undo a soft delete, requires users:reactivate.
export const reactivateUserApi = (userEmail: string) =>
    api.patch<ManagedUserRead>(`/users/${encodeURIComponent(userEmail)}/reactivate`);

export const updateUserRoleApi = (userEmail: string, role: string) =>
    api.patch(`/users/${encodeURIComponent(userEmail)}/role`, { role });
