/**
 * Shape of a successful GET /auth/me response (see
 * backend/mystic_auth/auth/current_user/current_user_handler.py). `permissions` is a
 * flat list of every action string granted unconditionally by the user's
 * active policies (e.g. "users:read_own"). It carries no per-resource
 * ownership/time/network granularity, so instance-level checks still need a
 * real call to POST /authorization/batch-check rather than this cached list.
 */
export interface CurrentUserProfile {
    name: string;
    email: string;
    role: string | null;
    permissions: string[];
    /** False for an OAuth-only account (no usable password credential).
     *  See backend/mystic_auth/auth/current_user/current_user_handler.py. */
    has_password: boolean;
}
