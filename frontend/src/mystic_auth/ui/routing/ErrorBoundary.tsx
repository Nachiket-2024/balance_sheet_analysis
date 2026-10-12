import React from "react";

import { reportError } from "../../core/errorMonitoring";
import { Button } from "../buttons/Button";
import translations from "../../translations/translations";

interface ErrorBoundaryProps {
    children: React.ReactNode;
}

interface ErrorBoundaryState {
    hasError: boolean;
}

/**
 * Top-level React error boundary. Catches an otherwise-uncaught render/
 * lifecycle error anywhere in the tree below it and shows a recoverable
 * fallback instead of the whole app unmounting to a blank white screen.
 * Deliberately a class component: React has no hook equivalent for
 * getDerivedStateFromError/componentDidCatch.
 *
 * Does not catch errors in event handlers or async code (a rejected promise
 * or a thrown error inside an onClick handler never reaches an error
 * boundary), so those still need their own try/catch. Mounted once at the
 * app root (main.tsx), outside the router, so it also catches an error
 * thrown before routing gets a chance to render.
 */
class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    state: ErrorBoundaryState = { hasError: false };

    static getDerivedStateFromError(): ErrorBoundaryState {
        return { hasError: true };
    }

    componentDidCatch(error: unknown, errorInfo: React.ErrorInfo): void {
        console.error("Unhandled render error:", error, errorInfo);
        // A no-op unless VITE_SENTRY_DSN is set, see core/errorMonitoring.ts.
        reportError(error, { componentStack: errorInfo.componentStack });
    }

    render(): React.ReactNode {
        if (!this.state.hasError) {
            return this.props.children;
        }

        return (
            <div className="flex items-center justify-center h-screen bg-bg-canvas px-4 text-center">
                <div className="flex flex-col items-center gap-4">
                    {/* fontSize 2xl / lineHeight 2rem, matching the app's "2xl" text style. */}
                    <h1 className="text-fg-error text-2xl leading-8 font-semibold">{translations.t("ui_text:errorBoundary.title")}</h1>

                    <p className="text-xl font-medium">
                        {translations.t("ui_text:errorBoundary.description")}
                    </p>

                    <Button
                        variant="brand"
                        size="md"
                        className="font-bold"
                        // A full navigation, not client-side routing: the
                        // React tree is in an unknown state after a render
                        // crash, so a fresh document load is the only
                        // reliably clean recovery.
                        onClick={() => window.location.assign("/")}
                    >
                        {translations.t("ui_text:errorBoundary.reload")}
                    </Button>
                </div>
            </div>
        );
    }
}

export default ErrorBoundary;
