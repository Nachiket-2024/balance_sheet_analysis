import axios from "axios";

import translations from "../translations/translations";

/**
 * Shared helper for TanStack Query mutation catch blocks: pulls a
 * human-readable message out of a failed axios request, falling back to a
 * caller-supplied message for anything else (network failure, non-axios
 * error, missing body).
 *
 * Checks two response shapes, since this backend uses both:
 *   - `{ error: string, code?: string }`: this app's own custom auth handlers
 *     (login/logout/signup/etc.).
 *   - `{ detail: string, code?: string, params?: object }`: FastAPI's
 *     default HTTPException shape, extended by backend/mystic_auth/core/errors.py's
 *     AppError for routes that have been migrated to it. `detail` can also
 *     be a list of Pydantic validation error objects (422s) rather than a
 *     string. That shape is deliberately NOT stringified here and falls
 *     through to `fallback`, since showing the caller a decent generic
 *     message beats dumping raw validation internals into a toast.
 *
 * When `code` is present, it's looked up in the "errors" translations namespace
 * (translations/languages/*\/errors.json) and rendered in the user's chosen
 * language, interpolated with `params` (e.g. a policy name) - this is the
 * one place backend error strings get translated, rather than every mutation
 * call site needing its own lookup. Routes not yet migrated to AppError have
 * no `code`, so this falls back to the raw (English) `error`/`detail`
 * string exactly as before.
 *
 * A `code` present but missing from errors.json (someone added a new
 * AppError downstream and forgot the translation - see
 * docs/mystic_auth/translations/overview.md) still degrades to the raw
 * English string below, so a real caller never sees a blank/broken toast.
 * But that degradation looks identical to "working as intended" at a
 * glance, so the dev console gets a loud warning too: the gap should be
 * caught the first time someone exercises that code path in development,
 * not discovered later from a bug report.
 */
export function extractApiErrorMessage(error: unknown, fallback: string): string {
    if (axios.isAxiosError(error)) {
        const data = error.response?.data;

        const code = data?.code;
        if (typeof code === "string") {
            const translationKey = `errors:${code}`;
            if (translations.exists(translationKey)) {
                return translations.t(translationKey, data?.params ?? {}) as string;
            }
            if (import.meta.env.DEV) {
                console.error(
                    `[translations] No entry for error code "${code}" in translations/languages/*/errors.json - ` +
                        "add one so this doesn't silently fall back to the raw English message."
                );
            }
        }

        const serverMessage = data?.error ?? data?.detail;
        if (typeof serverMessage === "string" && serverMessage.length > 0) {
            return serverMessage;
        }
    }
    return fallback;
}
