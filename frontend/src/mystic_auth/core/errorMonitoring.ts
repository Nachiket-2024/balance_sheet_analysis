import * as Sentry from "@sentry/react";

const dsn = import.meta.env.VITE_SENTRY_DSN;

// Initializes the Sentry SDK if VITE_SENTRY_DSN is set at build time, otherwise a
// no-op. Call once before the app renders (see main.tsx). Works with Sentry itself or
// any self-hosted server speaking the same protocol (e.g. Bugsink, see
// docs/mystic_auth/error-monitoring/overview.md).
export function initErrorMonitoring(): void {
    if (!dsn) return;

    Sentry.init({
        dsn,
        environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || import.meta.env.MODE,
        // No tracing/performance sampling needed here, so every event is an
        // intentional reportError() call or Sentry's own uncaught-error hook.
        tracesSampleRate: 0,
    });
}

// Reports an error to the configured error-monitoring server. Safe to call even if
// initErrorMonitoring() never ran; short-circuits the same way the backend's
// error_monitoring/sentry_service.py::capture_exception does. Used by
// ui/routing/ErrorBoundary.tsx, and available for feature code that catches its own
// noteworthy errors.
export function reportError(error: unknown, extra?: Record<string, unknown>): void {
    if (!dsn) return;

    Sentry.captureException(error, extra ? { extra } : undefined);
}
