import React, { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { useAuthStore } from "../../store/authStore";

// theme/tailwind.css's --duration-fast/--easing-hover (same tier
// StatTile/PasswordStrengthPanel use), so "how snappy the app feels" stays
// retunable from one place.
const ROUTE_FADE_TRANSITION = "opacity var(--duration-fast) var(--easing-hover)";

/**
 * Fades each route's content in on a client-side navigation instead of the
 * hard cut a bare `<Routes>` produces. Re-triggers on every pathname change
 * after the first: starts at opacity 0, then flips to 1 on the next
 * animation frame so the browser applies the CSS transition instead of
 * skipping to the end state. Plain CSS, no animation library - see App.tsx
 * for where this wraps `<Routes>`.
 *
 * Deliberately skipped for the very first render (isInitialRender below):
 * that one is the static boot-shell's own handoff, not a route change, and
 * fading content in on top of it added a second, animated visual state
 * between "boot shell" and "real page" - on top of the boot shell's own
 * removal, some visitors reported seeing this as two distinct loading
 * screens rather than one clean cut. The very first paint after the boot
 * shell now always renders at opacity 1 immediately, with no fade.
 */
const RouteFadeIn: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { pathname } = useLocation();
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
    const [visible, setVisible] = useState(true);
    const [isInitialRender, setIsInitialRender] = useState(true);

    // The opacity-0 reset happens during render (same "adjust during
    // render" pattern PolicyFormDialog.tsx uses) - only the rAF scheduling
    // (genuinely async, browser-timed) belongs in the effect.
    const [prevPathname, setPrevPathname] = useState(pathname);
    if (pathname !== prevPathname) {
        setPrevPathname(pathname);
        setIsInitialRender(false);
        setVisible(false);
    }

    useEffect(() => {
        const releaseBootShell = () => {
            const routeContent = document.querySelector('[data-route-content="true"]');
            if (!routeContent?.firstElementChild) return false;
            document.getElementById("boot-shell")?.remove();
            return true;
        };
        let observer: MutationObserver | undefined;
        const frame = requestAnimationFrame(() => {
            setVisible(true);
            // An authenticated visitor briefly reaches /login before the
            // login page redirects to /dashboard. Keep the boot surface over
            // that redirect so the later dashboard route can provide the
            // first measured content instead of exposing a late greeting.
            if (pathname !== "/login" || isAuthenticated === false) {
                if (!releaseBootShell()) {
                    observer = new MutationObserver(() => {
                        if (releaseBootShell()) observer?.disconnect();
                    });
                    observer.observe(document.getElementById("root") ?? document.body, { childList: true, subtree: true });
                }
            }
        });
        return () => {
            cancelAnimationFrame(frame);
            observer?.disconnect();
        };
    }, [isAuthenticated, pathname]);

    return (
        <div
            data-route-content="true"
            style={
                isInitialRender
                    ? undefined
                    : { opacity: visible ? 1 : 0, transition: ROUTE_FADE_TRANSITION }
            }
        >
            {children}
        </div>
    );
};

export default RouteFadeIn;
