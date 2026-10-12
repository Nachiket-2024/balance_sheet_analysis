import React from "react";

import { cn } from "../styles/classNames";

interface SectionHeadingProps extends React.ComponentPropsWithoutRef<"h2"> {
    /** "card" (18px/text-lg, the default): this heading is the only/main
     * title of its own standalone Card (ChangePasswordCard, AppearanceCard,
     * DeleteAccountCard, AccountStatusCard's StatusSection, the Legal
     * card). "subsection" (16px/text-base): a heading for one section
     * inside a larger composite card that already has its own outer
     * context (OperationsShortcutsCard within DashboardPage, the login-activity
     * chart within Audit Log's Security Events tab). Matches the two
     * heading sizes already established across the app - see
     * .project/design.md's Typography section. */
    level?: "card" | "subsection";
    /** Renders an <h3> instead of <h2>, for a heading nested under another
     * heading in the same document outline (e.g. inside a tab panel that
     * already has its own <h1>/<h2>). Purely semantic - level controls the
     * visual size, as controls the tag. */
    as?: "h2" | "h3";
}

/**
 * Shared "card/section title" text style: font-semibold, -0.01em tracking,
 * and one of two sizes (see `level`). Before this component, six files hand
 * -wrote `text-lg font-semibold tracking-[-0.01em]` and three wrote the
 * text-base equivalent - copy-pasted markup instead of a shared definition,
 * which is exactly how these drifted out of sync with each other over time
 * (see git history around the Account Settings font-size fixes). New
 * card/section headings should use this instead of hand-writing the classes
 * again.
 */
const SectionHeading = React.forwardRef<HTMLHeadingElement, SectionHeadingProps>(
    ({ level = "card", as = "h2", className, children, ...props }, ref) => {
        const Comp = as;
        return (
            <Comp
                ref={ref as never}
                className={cn(
                    "font-semibold tracking-[-0.01em]",
                    level === "card" ? "text-lg" : "text-base",
                    className
                )}
                {...props}
            >
                {children}
            </Comp>
        );
    }
);
SectionHeading.displayName = "SectionHeading";

export default SectionHeading;
