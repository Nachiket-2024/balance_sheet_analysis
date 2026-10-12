// Shape of a successful GET /auth/me response (see
// backend/mystic_auth/auth/current_user/current_user_handler.py).
export interface CurrentUserProfile {
    name: string;
    email: string;
    role: string | null;
    /** Flat list of action strings granted unconditionally by the user's active
     *  policies (e.g. "users:read_own"). No per-resource ownership/time/network
     *  granularity, so instance-level checks still need POST /authorization/batch-check
     *  rather than this cached list. */
    permissions: string[];
    /** False for an OAuth-only account (no usable password credential). */
    has_password: boolean;
    created_at: string;
    /** Count of this user's currently-live refresh tokens (devices/browsers with an
     *  active session), from the Valkey-backed registry. */
    active_sessions: number;
    /** Per-user brand color override (#rrggbb). null = using the app
     *  default scale (app/theme.ts). See appearanceStore.ts. */
    brand_color: string | null;
}
