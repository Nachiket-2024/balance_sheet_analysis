import React from "react";

import { cn } from "../styles/classNames";

type CardProps = React.ComponentPropsWithoutRef<"div"> & {
    /** Supports semantic article cards as well as StatTile-style clickable cards. */
    as?: "div" | "article" | "button";
    type?: string;
};

/**
 * The app's standard surface styling (theme tokens, rounded corners,
 * shadow) as a plain element: bg-bg-surface/border-border-card/
 * rounded-card/shadow-card/p-[20px_22px] map 1:1 to theme/tailwind.css's
 * --bg-surface/--border-card/--radius-card/--shadow-card/
 * --spacing-card-padding. Callers override via className (twMerge in
 * cn() lets a later class like "p-0" win over the default p).
 */
const Card = React.forwardRef<HTMLDivElement | HTMLButtonElement, CardProps>(
    ({ as = "div", className, children, ...props }, ref) => {
        const Comp = as;
        // as="button" needs button-only attrs (type) that a div-typed props object can't carry.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const polymorphicProps = props as any;
        return (
            <Comp
                ref={ref as never}
                className={cn(
                    "rounded-card border border-border-card bg-bg-surface p-[20px_22px] shadow-card transition-[border-color,box-shadow,background-color] duration-[var(--duration-base)] hover:shadow-card-hover",
                    className
                )}
                {...polymorphicProps}
            >
                {children}
            </Comp>
        );
    }
);
Card.displayName = "Card";

export default Card;
