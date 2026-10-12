import React from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../styles/classNames";
import { useLanguageStore } from "../../store/languageStore";
import { formatNumber } from "../../translations/numerals";

export interface StatTileProps {
    label: string;
    value: number | undefined;
    isLoading: boolean;
    color?: string;
    /** Applies a filter (or other action) tied to this tile when given - the
     * tile becomes a clickable shortcut instead of a read-only number. Omit
     * for a tile with no corresponding action. */
    onClick?: () => void;
    /** Overrides the default `Filter: {label}` aria-label used when onClick
     * is given, for callers that want more specific wording. */
    ariaLabel?: string;
}

/** A single labeled number in a summary card (UserStatsCard, PolicyStatsCard):
 * a large colored value with a muted label beneath it, optionally clickable. */
const StatTile: React.FC<StatTileProps> = ({ label, value, isLoading, color, onClick, ariaLabel }) => {
    const { t } = useTranslation("ui_text");
    // chromeLanguage, not pageLanguage: numerals stay ASCII even in a mixed
    // "en+hi" mode, same as dates (dateFormatters.ts).
    const language = useLanguageStore((s) => s.chromeLanguage);
    const Comp = onClick ? "button" : "div";
    return (
        <Comp
            className={cn(
                "text-center rounded-md py-1",
                onClick &&
                    // bg-brand-selected is a light tinted wash that sits behind
                    // existing text colors instead of replacing them - a solid
                    // fill would wash out both the colored number and the
                    // muted label at once.
                    "cursor-pointer border border-transparent transition-colors hover:bg-brand-selected hover:border-brand-solid focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-solid focus-visible:outline-offset-2",
            )}
            {...(onClick && {
                type: "button" as const,
                onClick,
                "aria-label": ariaLabel ?? t("filterLabel", { label }),
            })}
        >
            {isLoading ? (
                // bg-muted, not the default skeleton bg-emphasized: this tile
                // sits inside a Card (bg-surface), and in dark mode
                // bg-emphasized resolves to the same gray as bg-surface,
                // making the skeleton invisible even mid-pulse.
                <div className="h-8 w-12 mx-auto rounded-md bg-muted animate-pulse" />
            ) : (
                <p className={cn("text-3xl font-bold leading-none", color ?? "text-foreground")} style={color?.startsWith("#") ? { color } : undefined}>
                    {formatNumber(value, language)}
                </p>
            )}
            <p className="text-base text-muted-foreground mt-1 whitespace-nowrap">{label}</p>
        </Comp>
    );
};

export default StatTile;
