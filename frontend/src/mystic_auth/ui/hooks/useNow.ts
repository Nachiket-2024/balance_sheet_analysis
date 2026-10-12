import { useEffect, useState } from "react";

/** The current time in ms, refreshed every `intervalMs`, so relative times
 * like "2 minutes ago" keep counting up while the page stays open. */
export function useNow(intervalMs: number): number {
    const [now, setNow] = useState(() => Date.now());

    useEffect(() => {
        const id = window.setInterval(() => setNow(Date.now()), intervalMs);
        return () => window.clearInterval(id);
    }, [intervalMs]);

    return now;
}
