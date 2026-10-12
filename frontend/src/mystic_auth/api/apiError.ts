import axios from "axios";

import translations from "../translations/translations";

// Turns a backend error `code` into a translated message via the "errors" namespace
// (translations/languages/*/errors.json). Factored out of extractApiErrorMessage so
// callers with just a code (e.g. a `?error=<code>` redirect param, see
// OAuth2LoginButton.tsx) can reuse the same lookup. Returns null if there's nothing
// to translate, so callers can chain their own fallback.
//
// A code missing from errors.json falls back to the raw English message rather than
// breaking the toast, but that failure is silent otherwise, so we also warn in DEV.
export function translateErrorCode(code: unknown, params?: Record<string, unknown>): string | null {
    if (typeof code !== "string") {
        return null;
    }

    const translationKey = `errors:${code}`;
    if (translations.exists(translationKey)) {
        return translations.t(translationKey, params ?? {}) as string;
    }

    if (import.meta.env.DEV) {
        console.error(
            `[translations] No entry for error code "${code}" in translations/languages/*/errors.json - ` +
                "add one so this doesn't silently fall back to the raw English message."
        );
    }
    return null;
}

// True if a request failed with a 403 from the backend's permission check. Used to
// show a friendly "you don't have permission" message instead of a generic error,
// for the rare case a permission got revoked after the page already loaded.
export function isForbiddenError(error: unknown): boolean {
    return axios.isAxiosError(error) && error.response?.status === 403;
}

// Pulls a readable message out of a failed axios request, for use in mutation catch
// blocks. Checks two response shapes this backend uses: `{ error, code? }` (this
// app's own auth handlers) and `{ detail, code?, params? }` (FastAPI's HTTPException,
// extended by AppError). `detail` can also be a list of Pydantic validation errors
// (422s); that shape isn't stringified, it falls through to `fallback` instead.
export function extractApiErrorMessage(error: unknown, fallback: string): string {
    if (axios.isAxiosError(error)) {
        const data = error.response?.data;

        const translated = translateErrorCode(data?.code, data?.params);
        if (translated) {
            return translated;
        }

        const serverMessage = data?.error ?? data?.detail;
        if (typeof serverMessage === "string" && serverMessage.length > 0) {
            return serverMessage;
        }
    }
    return fallback;
}
