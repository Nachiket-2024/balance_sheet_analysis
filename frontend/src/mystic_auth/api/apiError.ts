import axios from "axios";

/**
 * Shared helper for TanStack Query mutation catch blocks: pulls a
 * human-readable message out of a failed axios request, falling back to a
 * caller-supplied message for anything else (network failure, non-axios
 * error, missing body).
 *
 * Checks two response shapes, since this backend uses both:
 *   - `{ error: string }`: this app's own custom auth handlers
 *     (login/logout/signup/etc.).
 *   - `{ detail: string }`: FastAPI's default HTTPException shape.
 *     `detail` can also be a list of Pydantic validation error objects
 *     (422s) rather than a string. That shape is deliberately NOT
 *     stringified here and falls through to `fallback`, since showing the
 *     caller a decent generic message beats dumping raw validation
 *     internals into a toast.
 */
export function extractApiErrorMessage(error: unknown, fallback: string): string {
    if (axios.isAxiosError(error)) {
        const data = error.response?.data;
        const serverMessage = data?.error ?? data?.detail;
        if (typeof serverMessage === "string" && serverMessage.length > 0) {
            return serverMessage;
        }
    }
    return fallback;
}
