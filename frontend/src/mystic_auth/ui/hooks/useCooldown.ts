import { useEffect, useRef, useState } from "react";

/**
 * Countdown-in-seconds used by every "resend" form (password reset request,
 * verification email request) to rate-limit repeat submissions. The interval
 * is tracked in a ref and cleared on unmount, so navigating away mid-cooldown
 * can't leak an interval calling setState on an unmounted component.
 */
export function useCooldown() {
    const [cooldown, setCooldown] = useState(0);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    useEffect(() => {
        return () => {
            if (intervalRef.current !== null) {
                clearInterval(intervalRef.current);
            }
        };
    }, []);

    const start = (seconds = 60) => {
        setCooldown(seconds);

        intervalRef.current = setInterval(() => {
            setCooldown((prev) => {
                if (prev <= 1) {
                    if (intervalRef.current !== null) {
                        clearInterval(intervalRef.current);
                        intervalRef.current = null;
                    }
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);
    };

    return { cooldown, startCooldown: start };
}
