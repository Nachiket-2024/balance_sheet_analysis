import { useEffect } from "react";

/**
 * Warns the user via the browser's native "leave site?" prompt if they try
 * to close the tab/reload/navigate away with unsaved edits still pending,
 * e.g. AccountSettingsPage's name/password fields. Only wires the listener
 * while `isDirty` is true, so it never fires for a form with nothing to lose.
 */
export function useUnsavedChangesWarning(isDirty: boolean): void {
    useEffect(() => {
        if (!isDirty) return;

        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            e.preventDefault();
        };

        window.addEventListener("beforeunload", handleBeforeUnload);
        return () => window.removeEventListener("beforeunload", handleBeforeUnload);
    }, [isDirty]);
}
