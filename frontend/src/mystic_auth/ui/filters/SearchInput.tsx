import React from "react";
import { Loader2 } from "lucide-react";

import { Input } from "../shadcn/input";
import { cn } from "../styles/classNames";
import { SEARCH_QUERY_MAX_LENGTH } from "../styles/inputStyles";

interface SearchInputProps
    extends Omit<React.ComponentPropsWithoutRef<"input">, "value" | "onChange" | "size"> {
    value: string;
    onChange: (value: string) => void;
    /** True while a request this value drives is in flight. Omit (or pass
     * false) for a purely client-side/synchronous filter (e.g.
     * PermissionsPage's in-memory catalog search), where there's never a
     * meaningful "still fetching" gap worth showing. */
    isFetching?: boolean;
    /** Total matching rows for the current value, once known. Undefined
     * (the default, before a response has come back) shows nothing. */
    totalResults?: number;
    /** Renders the pluralized "N results" text for a given count - each
     * caller passes its own translated string (e.g.
     * `(count) => t("users:page.resultsCount", { count })`) since the
     * wording and i18next namespace differ per page. */
    resultsLabel: (count: number) => string;
    /** aria-label for the spinner shown while isFetching, e.g. t("ui_text:loading"). */
    loadingLabel: string;
    /** "sm" shortens the box for a tighter filter row (audit log sections). Defaults to "md". */
    size?: "sm" | "md";
    /** Sizes/positions the whole search box - a Tailwind width/margin class string, e.g. "w-40" or "mb-4". Defaults to max-w-sm. */
    className?: string;
}

/**
 * Search box shared by every server-searched (or, with isFetching omitted,
 * client-filtered) list page: UsersFilterBar, PoliciesFilterBar,
 * RateLimitsFilterBar, SecurityFilterBar, PermissionsFilterBar. Shows a
 * spinner while a request is in flight, then the matching-row count once it
 * resolves, inside the box's own right edge - not as a separate element next
 * to it, and only while there's actual text in the box. Without this, typing
 * a search/filter value that doesn't visibly change the current page's rows
 * (e.g. it only affects which page 2+ would show) looks like it silently did
 * nothing; showing a leftover count after clearing the box back to empty
 * (stale until the unfiltered refetch resolves, then just irrelevant once it
 * does) would look just as broken, so the hint is gated on the box being
 * non-empty rather than on the request being for "the current" value.
 */
const SearchInput: React.FC<SearchInputProps> = ({
    value, onChange, isFetching, totalResults, resultsLabel, loadingLabel, maxLength, size = "md", className, ...inputProps
}) => {
    const hasValue = value.trim() !== "";
    return (
        // A fixed width, not just a max-width: this div is a flex item in
        // each filter bar's flex-wrap row with no flex-basis of its own, so
        // with only a max-width its auto flex-basis shrinks to fit the
        // current value's content, then grows again as more is typed -
        // the box visibly widens while typing. shrink-0 keeps it from being
        // squeezed back down by its siblings once at that width.
        <div className={cn("relative w-72 shrink-0", className)}>
            <Input
                value={value}
                onChange={(e) => onChange(e.target.value)}
                maxLength={maxLength ?? SEARCH_QUERY_MAX_LENGTH}
                className={cn(
                    "bg-bg-surface border-border-strong hover:border-brand-500 hover:bg-brand-100",
                    "dark:hover:border-brand-400 dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_16%,transparent)]",
                    "focus-visible:border-brand-solid focus-visible:ring-brand-solid/50",
                    hasValue && "pr-24",
                    size === "sm" ? "h-8 text-sm" : "h-9"
                )}
                {...inputProps}
            />
            {hasValue && (
                <div
                    className="absolute inset-y-0 right-3 flex items-center gap-1.5 text-sm text-fg-muted"
                    role="status"
                    aria-live="polite"
                >
                    {isFetching ? (
                        <Loader2 className="size-3.5 animate-spin" aria-label={loadingLabel} />
                    ) : (
                        totalResults !== undefined && <span>{resultsLabel(totalResults)}</span>
                    )}
                </div>
            )}
        </div>
    );
};

export default SearchInput;
