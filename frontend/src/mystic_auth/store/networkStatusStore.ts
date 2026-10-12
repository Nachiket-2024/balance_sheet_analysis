import { create } from "zustand";

interface NetworkStatusState {
    isOnline: boolean;
}

function getInitialIsOnline(): boolean {
    // jsdom (the test environment) implements navigator.onLine (defaulting to true),
    // but guard anyway for a future non-browser environment that doesn't expose it.
    if (typeof navigator === "undefined" || typeof navigator.onLine !== "boolean") return true;
    return navigator.onLine;
}

// Client-side state, not server state, so it lives in Zustand alongside
// themeStore/authStore rather than TanStack Query.
export const useNetworkStatusStore = create<NetworkStatusState>(() => ({
    isOnline: getInitialIsOnline(),
}));

// Module-level, not component-level: connectivity is one global browser signal for the
// app's whole lifetime, not state any single component owns. Unlike themeStore's
// one-time matchMedia read, this keeps listening since connectivity can flip mid-session.
if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
    window.addEventListener("online", () => useNetworkStatusStore.setState({ isOnline: true }));
    window.addEventListener("offline", () => useNetworkStatusStore.setState({ isOnline: false }));
}
