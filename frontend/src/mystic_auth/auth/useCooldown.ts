import { useEffect, useRef, useState } from "react";

/**
 * Countdown-in-seconds used by every "resend" form (password reset request,
 * verification email request) to rate-limit repeat submissions. The interval
 * is tracked in a ref and cleared on unmount: previously each form created
 * its own setInterval as a local variable inside start(), with nothing
 * clearing it if the component unmounted before the countdown finished
 * naturally (e.g. the user navigates away mid-cooldown) - a leaked interval
 * that kept calling setState on an unmounted component every second.
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
