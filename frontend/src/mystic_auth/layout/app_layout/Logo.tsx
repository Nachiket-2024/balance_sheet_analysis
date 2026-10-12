import React from "react";

import { APP_LOGO_URL, APP_NAME } from "../../core/settings";
import { useAppearanceStore } from "../../store/appearanceStore";
import { getBrandIconDataUri } from "../../theme/brandIcon";

interface LogoProps {
    /** "sm": Sidebar's compact header row. "md" (default): the brand mark
     * inside an auth-page card. */
    size?: "sm" | "md";
}

const SIZES = {
    sm: { badgeHeight: "h-8", badge: "w-8 h-8", icon: 18, text: "text-xl" },
    md: { badgeHeight: "h-11", badge: "w-11 h-11", icon: 22, text: "text-2xl" },
} as const;

/**
 * Brand mark: icon badge plus wordmark. Defaults to `/favicon.svg`, the same
 * file the browser tab icon uses. Once a user picks a brand color
 * (appearanceStore.ts), both this badge and the tab icon render from
 * `getBrandIconDataUri` (theme/brandIcon.ts) instead, so they stay in sync.
 * Set VITE_APP_LOGO_URL to swap in a full custom logo (affects this mark
 * only, not the tab icon; replace public/favicon.svg for that).
 */
const Logo: React.FC<LogoProps> = ({ size = "md" }) => {
    const s = SIZES[size];
    const brandColor = useAppearanceStore((state) => state.brandColor);

    if (APP_LOGO_URL) {
        // Height only (matches the original h={s.badge}, not boxSize): a
        // custom logo's own width should follow its natural aspect ratio,
        // not get forced square like the generated icon badge below.
        return <img src={APP_LOGO_URL} alt={APP_NAME} className={s.badgeHeight} />;
    }

    return (
        // justify-center: self-centers regardless of whether the parent
        // stretches to full width, so callers don't need items-center.
        <div className={`flex items-center justify-center ${size === "sm" ? "gap-2" : "gap-3"}`}>
            <img
                src={brandColor ? getBrandIconDataUri(brandColor) : "/favicon.svg"}
                alt=""
                className={`shrink-0 ${s.badge}`}
            />
            <span className={`${s.text} font-bold text-brand-fg tracking-tight`}>
                {APP_NAME}
            </span>
        </div>
    );
};

export default Logo;
