import * as Sentry from "@sentry/react";

const dsn = import.meta.env.VITE_SENTRY_DSN;

/**
 * Initializes the Sentry SDK if VITE_SENTRY_DSN is set at build time; a
 * complete no-op otherwise, so this template behaves identically whether
 * or not error monitoring is wired up. Call once, before the app renders
 * (see main.tsx).
 *
 * Works against Sentry itself or any self-hosted server that speaks the
 * same protocol (e.g. Bugsink, see docs/mystic_auth/error-monitoring/overview.md); nothing
 * here is Sentry-the-company-specific beyond the SDK package name.
 */
export function initErrorMonitoring(): void {
    if (!dsn) return;

    Sentry.init({
        dsn,
        environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || import.meta.env.MODE,
        // This template has no other use for tracing/performance sampling,
        // sending 0% keeps every event an intentional reportError() call
        // (below, or Sentry's own automatic uncaught-error/unhandled-
        // rejection hooks) rather than adding request-tracing overhead
        // nobody asked for. Error capture itself is unaffected.
        tracesSampleRate: 0,
    });
}

/**
 * Reports error to the configured error-monitoring server. Safe to call
 * even when initErrorMonitoring() was never invoked (VITE_SENTRY_DSN
 * unset): the SDK itself no-ops when uninitialized, but this also
 * short-circuits before touching the SDK at all, matching the backend's
 * equivalent (error_monitoring/sentry_service.py::capture_exception).
 *
 * Called from ui/ErrorBoundary.tsx for a caught render error; also
 * available for your own feature code to report a caught-but-still-
 * noteworthy error the same way.
 */
export function reportError(error: unknown, extra?: Record<string, unknown>): void {
    if (!dsn) return;

    Sentry.captureException(error, extra ? { extra } : undefined);
}
