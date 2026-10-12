import React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../styles/classNames";

/**
 * Chip styling per color x variant. Every variant (not just outline) keeps a
 * visible, matching-hue border: a borderless subtle/solid chip on this
 * app's light bg.surface/bg.canvas reads as a barely-there smudge for
 * several colors (gray, yellow) without one. brand/accent reuse the
 * semantic border/subtle/solid/fg tokens from theme/tailwind.css (so they
 * follow a signed-in user's own brand-color pick); the stock palettes below
 * use Tailwind's built-in scale directly, at the same 200/900 (subtle) and
 * 300/700 (outline/border) steps tailwind.css's red/orange/green/
 * blue/purple/teal/gray ".subtle" tokens used.
 */
const badgeVariants = cva("inline-flex w-fit items-center gap-1 whitespace-nowrap rounded-md border font-semibold", {
    variants: {
        size: {
            xs: "px-1.5 py-0.5 text-[10px] leading-none",
            sm: "px-2 py-0.5 text-xs",
            md: "px-2.5 py-1 text-sm",
            lg: "px-3 py-1.5 text-sm",
        },
        color: {
            brand: "",
            gray: "",
            red: "",
            green: "",
            yellow: "",
            orange: "",
            cyan: "",
        },
        variant: {
            subtle: "",
            solid: "",
            outline: "bg-transparent",
        },
    },
    compoundVariants: [
        { color: "brand", variant: "subtle", class: "bg-brand-subtle text-brand-fg border-brand-border" },
        { color: "brand", variant: "solid", class: "bg-brand-solid text-brand-contrast border-brand-border" },
        { color: "brand", variant: "outline", class: "text-brand-fg border-brand-border" },

        { color: "gray", variant: "subtle", class: "bg-gray-200 text-gray-800 border-gray-300 dark:bg-gray-800 dark:text-gray-200 dark:border-gray-700" },
        { color: "gray", variant: "solid", class: "bg-gray-700 text-white border-gray-700 dark:bg-gray-300 dark:text-gray-900 dark:border-gray-300" },
        { color: "gray", variant: "outline", class: "text-gray-700 border-gray-400 dark:text-gray-300 dark:border-gray-600" },

        { color: "red", variant: "subtle", class: "bg-red-200 text-red-900 border-red-300 dark:bg-red-900 dark:text-red-200 dark:border-red-700" },
        { color: "red", variant: "solid", class: "bg-red-600 text-white border-red-600" },
        { color: "red", variant: "outline", class: "text-red-700 border-red-500 dark:text-red-300 dark:border-red-600" },

        { color: "green", variant: "subtle", class: "bg-green-200 text-green-900 border-green-300 dark:bg-green-900 dark:text-green-200 dark:border-green-700" },
        { color: "green", variant: "solid", class: "bg-green-600 text-white border-green-600" },
        { color: "green", variant: "outline", class: "text-green-700 border-green-500 dark:text-green-300 dark:border-green-600" },

        { color: "yellow", variant: "subtle", class: "bg-yellow-200 text-yellow-900 border-yellow-300 dark:bg-yellow-900 dark:text-yellow-200 dark:border-yellow-700" },
        { color: "yellow", variant: "solid", class: "bg-yellow-500 text-yellow-950 border-yellow-500" },
        { color: "yellow", variant: "outline", class: "text-yellow-700 border-yellow-500 dark:text-yellow-300 dark:border-yellow-600" },

        { color: "orange", variant: "subtle", class: "bg-orange-200 text-orange-900 border-orange-300 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700" },
        { color: "orange", variant: "solid", class: "bg-orange-600 text-white border-orange-600" },
        { color: "orange", variant: "outline", class: "text-orange-700 border-orange-500 dark:text-orange-300 dark:border-orange-600" },

        { color: "cyan", variant: "subtle", class: "bg-cyan-200 text-cyan-900 border-cyan-300 dark:bg-cyan-900 dark:text-cyan-200 dark:border-cyan-700" },
        { color: "cyan", variant: "solid", class: "bg-cyan-600 text-white border-cyan-600" },
        { color: "cyan", variant: "outline", class: "text-cyan-700 border-cyan-500 dark:text-cyan-300 dark:border-cyan-600" },
    ],
    defaultVariants: {
        size: "md",
        color: "gray",
        variant: "subtle",
    },
});

export interface BadgeProps
    extends React.ComponentPropsWithoutRef<"span">,
        Omit<VariantProps<typeof badgeVariants>, "color"> {
    /** Named "colorPalette" (not "color") for consistent naming across every call site. */
    colorPalette?: VariantProps<typeof badgeVariants>["color"];
}

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
    ({ className, colorPalette, size, variant, ...props }, ref) => (
        <span ref={ref} className={cn(badgeVariants({ color: colorPalette, size, variant }), className)} {...props} />
    )
);
Badge.displayName = "Badge";

export default Badge;
