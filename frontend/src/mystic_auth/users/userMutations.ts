import { useMutation } from "@tanstack/react-query";

import {
    updateUserApi,
    deleteUserApi,
    purgeUserApi,
    reactivateUserApi,
    updateUserRoleApi,
    type UserUpdatePayload,
    type ManagedUserRead,
} from "../api/users_api";
import { extractApiErrorMessage } from "../api/apiError";
import { queryClient } from "../core/queryClient";
import { USERS_QUERY_KEY } from "./userQueries";

/**
 * Each mutation invalidates the shared users list on success: the User
 * Management page's table is a TanStack Query cache read, not local state,
 * so a management action here is reflected everywhere that list is rendered.
 */
export function useUpdateUserMutation() {
    return useMutation<ManagedUserRead, Error, { userEmail: string; payload: UserUpdatePayload }>({
        mutationFn: async ({ userEmail, payload }) => {
            try {
                return (await updateUserApi(userEmail, payload)).data;
            } catch (error) {
                throw new Error(extractApiErrorMessage(error, "Failed to update user"), { cause: error });
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
        },
    });
}

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
