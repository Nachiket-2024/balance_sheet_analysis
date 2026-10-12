import { create } from "zustand";

// Every store this factory creates registers its own reset here, so tests can wipe all
// of them at once (see __tests__/setup.ts) without each test file needing to know which
// page stores exist. Never touched in production: nothing here calls resetAllSessionUiStores.
const resetters: Array<() => void> = [];

export function resetAllSessionUiStores(): void {
    resetters.forEach((reset) => reset());
}

/**
 * Factory for a page's "where did I leave this" UI state: active tab,
 * filters, sort, etc. Deliberately in-memory only (no localStorage), unlike
 * languageStore/themeStore - these values shouldn't survive a full reload or
 * follow a different user who logs in on the same browser later, but they
 * should survive ordinary in-app navigation away from the page and back,
 * which a plain component useState cannot do (it resets on unmount).
 *
 * Each page still reads its own `?tab=`/`?search=`/etc. URL param first, as
 * a one-shot deep-link override (see AccountSettingsPage/AuditLogPage/
 * PermissionsPage's matching comments) - this store is only the fallback
 * once there's no such override, and the value future page visits reuse.
 */
export function createSessionUiStore<T extends object>(initial: T) {
    const store = create<T & { update: (patch: Partial<T>) => void }>((set) => ({
        ...initial,
        update: (patch) => set(patch as Partial<T & { update: (patch: Partial<T>) => void }>),
    }));
    // Merge, not replace: replacing would also drop `update` itself, which isn't part of `initial`.
    resetters.push(() => store.setState({ ...initial }));
    return store;
}
