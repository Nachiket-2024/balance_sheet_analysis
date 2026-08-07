import api from "../api/axiosInstance";
import type { ManagedUserRead, UserUpdatePayload } from "../api/users_api";

export const updateMyAccountApi = (payload: UserUpdatePayload) => api.put<ManagedUserRead>("/users/me", payload);
