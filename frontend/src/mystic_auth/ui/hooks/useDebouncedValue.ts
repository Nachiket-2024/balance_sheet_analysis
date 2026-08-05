import { useEffect, useState } from "react";

/**
 * Returns `value`, but only after it's stopped changing for `delayMs`. Used
 * for search inputs backed by a server round-trip (unlike Users/Policies'
 * old fully-client-side filter, a keystroke here means a real request), so
 * typing doesn't fire one request per character.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
    const [debounced, setDebounced] = useState(value);

    useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), delayMs);
        return () => clearTimeout(timer);
    }, [value, delayMs]);

    return debounced;
}
