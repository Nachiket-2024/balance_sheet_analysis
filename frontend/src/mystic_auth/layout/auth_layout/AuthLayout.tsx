import React from "react";

import ControlCluster from "../controls/ControlCluster";
import { cn } from "../../ui/styles/classNames";

interface AuthLayoutProps {
    children: React.ReactNode;
    /**
     * "form" (default): vertically + horizontally centered, for login/signup/
     * reset-password style forms.
     * "status": horizontally centered but top-aligned with fixed top spacing,
     * for verification/confirmation/status pages whose content height varies.
     */
    variant?: "form" | "status";
}

/**
 * Shared shell for unauthenticated pages. The two-column treatment gives
 * short auth flows a product-quality home without making the form itself
 * longer; the right rail disappears on small screens to preserve space.
 */
const AuthLayout: React.FC<AuthLayoutProps> = ({ children, variant = "form" }) => {
    return (
        <div className="relative isolate flex min-h-screen overflow-x-hidden bg-bg-canvas bg-linear-to-br from-(--bg-canvas-from) to-(--bg-canvas-to)">
            <div
                aria-hidden="true"
                className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(740px_360px_at_18%_-10%,color-mix(in_srgb,var(--brand-solid)_16%,transparent),transparent_65%),radial-gradient(640px_320px_at_100%_8%,color-mix(in_srgb,var(--accent-solid)_14%,transparent),transparent_60%)] dark:bg-[radial-gradient(740px_360px_at_18%_-10%,color-mix(in_srgb,var(--brand-solid)_22%,transparent),transparent_65%),radial-gradient(640px_320px_at_100%_8%,color-mix(in_srgb,var(--accent-solid)_12%,transparent),transparent_60%)]"
            />
            {/* Normal document flow (not position="absolute"), so it reserves
                its own row height and never collides with a tall card's top
                edge on short viewports. */}
            <div className="absolute right-4 top-4 z-20 sm:right-6 sm:top-5">
                <div className="flex justify-end">
                    <ControlCluster />
                </div>
            </div>

            <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-1 flex-col">
                <main className={cn(
                    "flex min-h-screen w-full min-w-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-4 sm:px-6 lg:px-10 lg:py-4 [&>div>div]:p-4 lg:[&>div>div]:p-5 [&_form]:gap-2.5 [&_label]:text-sm [&_input]:h-10 [&_>div>div>div]:gap-2.5",
                    variant === "status" ? "lg:justify-start lg:pt-12" : ""
                )}>
                    <div className="flex w-full justify-center">{children}</div>
                </main>
            </div>
        </div>
    );
};

export default AuthLayout;
