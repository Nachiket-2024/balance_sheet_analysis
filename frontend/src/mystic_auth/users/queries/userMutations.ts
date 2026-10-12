import { useMutation } from "@tanstack/react-query";

import {
    deleteUserApi,
    purgeUserApi,
    reactivateUserApi,
    updateUserRoleApi,
    exportUsersApi,
    type ManagedUserRead,
    type ListUsersParams,
} from "../../api/users_api";
import { extractApiErrorMessage } from "../../api/apiError";
import { queryClient } from "../../core/queryClient";
import { USERS_QUERY_KEY } from "./userQueries";

/**
 * Each mutation invalidates the shared users list on success: the User
 * Management page's table is a TanStack Query cache read, not local state,
 * so a management action here is reflected everywhere that list is rendered.
 */
export function useDeleteUserMutation() {
    return useMutation<void, Error, { userEmail: string }>({
        mutationFn: async ({ userEmail }) => {
            try {
                await deleteUserApi(userEmail);
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to delete user"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
        },
    });
}

export function usePurgeUserMutation() {
    return useMutation<void, Error, { userEmail: string }>({
        mutationFn: async ({ userEmail }) => {
            try {
                await purgeUserApi(userEmail);
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to permanently remove user"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
        },
    });
}

export function useReactivateUserMutation() {
    return useMutation<ManagedUserRead, Error, { userEmail: string }>({
        mutationFn: async ({ userEmail }) => {
            try {
                return (await reactivateUserApi(userEmail)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to reactivate user"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
        },
    });
}

/** Extracts the server-picked filename (users_export_<timestamp>.csv, from
 * export_users' Content-Disposition header) instead of hardcoding one here. */
function filenameFromContentDisposition(contentDisposition: string | undefined): string {
    const match = contentDisposition?.match(/filename="([^"]+)"/);
    return match?.[1] ?? "users_export.csv";
}

export function useExportUsersMutation() {
    return useMutation<void, Error, ListUsersParams>({
        mutationFn: async (params) => {
            try {
                const response = await exportUsersApi(params);
                const filename = filenameFromContentDisposition(response.headers["content-disposition"]);
                const url = URL.createObjectURL(response.data);
                const link = document.createElement("a");
                link.href = url;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(url);
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to export users"), { cause: error });
            }
        },
    });
}

export function useUpdateUserRoleMutation() {
    return useMutation<unknown, Error, { userEmail: string; role: string }>({
        mutationFn: async ({ userEmail, role }) => {
            try {
                return (await updateUserRoleApi(userEmail, role)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to update role"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
        },
    });
}
