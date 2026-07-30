import api from "./axiosInstance";

export interface AdminUserRead {
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
    // already has one (self-service PUT /users/me only; the admin route
    // ignores it). Not needed when setting a password for the first time on
    // an OAuth-only account.
    current_password?: string;
}

export const listUsersApi = () => api.get<AdminUserRead[]>("/users/");

export const updateUserApi = (userEmail: string, payload: UserUpdatePayload) =>
    api.put<AdminUserRead>(`/users/${encodeURIComponent(userEmail)}`, payload);

// Soft delete (default, reversible): sets is_active=false + deleted_at,
// revokes active sessions, preserves the row and its audit history.
export const deleteUserApi = (userEmail: string) => api.delete(`/users/${encodeURIComponent(userEmail)}`);

// Hard delete (separate, irreversible operation): requires users:purge,
// a distinct and more sensitive permission from users:delete_any.
export const purgeUserApi = (userEmail: string) => api.delete(`/users/${encodeURIComponent(userEmail)}/purge`);

// Undo a soft delete, requires users:reactivate.
export const reactivateUserApi = (userEmail: string) =>
    api.patch<AdminUserRead>(`/users/${encodeURIComponent(userEmail)}/reactivate`);

export const updateUserRoleApi = (userEmail: string, role: string) =>
    api.patch(`/users/${encodeURIComponent(userEmail)}/role`, { role });
