import React from "react";

import { cn } from "../styles/classNames";

interface AuthResultPanelProps {
    icon: React.ReactNode;
    /** Matches design/auth.html's `.result-icon` variants: brand for a
     * neutral "we did something" result (email sent), success/error for an
     * outcome that needs its own status color. */
    variant: "brand" | "success" | "error";
    title: string;
    description: React.ReactNode;
    children?: React.ReactNode;
}

// Matches FormAlert's approach: shadcn ships no built-in status palette, so
// error/success colors are applied directly with their own dark: variants.
const VARIANT_CLASSES = {
    brand: "bg-brand-tile-subtle border-brand-solid text-brand-fg",
    success: "bg-green-100 border-green-500 text-fg-success dark:bg-green-950",
    error: "bg-red-100 border-red-500 text-fg-error dark:bg-red-950",
} as const;

/**
 * Replaces a form with a result state (signup/reset "check your email",
 * reset-password success/expired-link, forgot-password success) instead of
 * leaving the filled-in form visible and clickable alongside a banner.
 * Shared across signup, password_reset_request and password_reset_confirm
 * so all three "we sent you an email" / "here's what happened" states match.
 */
const AuthResultPanel: React.FC<AuthResultPanelProps> = ({ icon, variant, title, description, children }) => {
    return (
        <div
            className="flex flex-col items-center text-center gap-3 w-full"
            role={variant === "error" ? "alert" : "status"}
            aria-live={variant === "error" ? "assertive" : "polite"}
        >
            <div className={cn("w-14 h-14 rounded-full flex items-center justify-center border", VARIANT_CLASSES[variant])}>
                {icon}
            </div>
            <div className="flex flex-col gap-1">
                <p className="text-lg font-semibold">{title}</p>
                <p className="text-base text-muted-foreground break-words whitespace-pre-wrap">{description}</p>
            </div>
            {children && <div className="flex flex-col w-full gap-3 mt-1">{children}</div>}
        </div>
    );
};

export default AuthResultPanel;
