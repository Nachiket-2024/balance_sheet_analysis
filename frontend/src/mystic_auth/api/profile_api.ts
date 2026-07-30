import api from "../api/axiosInstance";
import type { AdminUserRead, UserUpdatePayload } from "../api/users_api";

export const updateMyProfileApi = (payload: UserUpdatePayload) => api.put<AdminUserRead>("/users/me", payload);
