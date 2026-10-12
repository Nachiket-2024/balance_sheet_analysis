import { useEffect } from "react";
import { useLocation } from "react-router";

/**
 * Scrolls the element whose `id` matches the current URL's `#hash` into
 * view once it exists in the DOM. Mounted once in AppLayout so every page
 * gets this for free - CommandPalette's content search can use it to land
 * on a specific in-page section via an extraSearchItems entry's `#hash`
 * destination (none of the built-in SEARCH_ITEMS need it right now; every
 * built-in destination is a whole tab/page instead).
 *
 * Retries briefly instead of running once: the target can still be mounting
 * (a lazy-loaded route chunk, a loading skeleton) when this effect first
 * runs, so a single `getElementById` right after navigation often finds nothing.
 */
export function useScrollToHash() {
    const { hash } = useLocation();

    useEffect(() => {
        if (!hash) return;
        const id = decodeURIComponent(hash.slice(1));
        let cancelled = false;
        let attempts = 0;

        const tryScroll = () => {
            if (cancelled) return;
            const el = document.getElementById(id);
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "start" });
                return;
            }
            if (attempts++ < 20) setTimeout(tryScroll, 100);
        };
        tryScroll();

        return () => {
            cancelled = true;
        };
    }, [hash]);
}
