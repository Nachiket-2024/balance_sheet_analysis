import React, { useEffect, useState } from "react";
import { CircleCheck, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useNetworkStatusStore } from "../../store/networkStatusStore";
import { cn } from "../styles/classNames";

// Same status->color mapping FormAlert.tsx uses (shadcn's Alert only ships
// "default"/"destructive", with no built-in status palette).
const STATUS_CLASSES = {
    success: "border-green-300 bg-green-50 text-green-800 dark:border-green-700 dark:bg-green-950 dark:text-green-200 [&>svg]:text-green-600 dark:[&>svg]:text-green-400",
    warning: "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-700 dark:bg-orange-950 dark:text-orange-200 [&>svg]:text-orange-600 dark:[&>svg]:text-orange-400",
};

// How long the "back online" confirmation stays up once shown: long enough
// to register as reassurance, short enough not to linger like permanent
// chrome would.
const RECONNECTED_BANNER_MS = 4000;

/**
 * Fixed banner reflecting networkStatusStore's isOnline flag, mounted once
 * at the app root. Without it, losing the connection only shows up as
 * scattered failed-request toasts; this gives it one unmissable source.
 *
 * Briefly confirms reconnection too (RECONNECTED_BANNER_MS), then hides
 * itself, same "temporary reassurance" reasoning as RouteProgressBar.
 */
const OfflineBanner: React.FC = () => {
    const { t } = useTranslation("ui_text");
    const isOnline = useNetworkStatusStore((s) => s.isOnline);

    const [lastSeenOnline, setLastSeenOnline] = useState(isOnline);
    const [showReconnected, setShowReconnected] = useState(false);

    // Adjust state during render (same pattern as ConfirmDialog.tsx), not an
    // effect, so a false->true reconnect right before unmount still
    // registers. Flipping back offline clears showReconnected immediately.
    if (isOnline !== lastSeenOnline) {
        setLastSeenOnline(isOnline);
        setShowReconnected(isOnline);
    }

    // The timer itself is a legitimate effect (scheduling/cleanup against
    // an external clock), unlike the synchronous state adjustment above.
    useEffect(() => {
        if (!showReconnected) return;
        const timeoutId = window.setTimeout(() => setShowReconnected(false), RECONNECTED_BANNER_MS);
        return () => window.clearTimeout(timeoutId);
    }, [showReconnected]);

    if (isOnline && !showReconnected) return null;

    const status = isOnline ? "success" : "warning";
    const Icon = isOnline ? CircleCheck : TriangleAlert;

    return (
        <div
            role="status"
            aria-live="polite"
            className={cn(
                "fixed bottom-0 inset-x-0 z-[2147483647] flex items-center justify-center gap-2 rounded-none border px-4 py-3 text-sm",
                STATUS_CLASSES[status]
            )}
        >
            <Icon size={16} aria-hidden="true" />
            <span className="font-medium">{isOnline ? t("offlineBanner.backOnline") : t("offlineBanner.offline")}</span>
        </div>
    );
};

export default OfflineBanner;
