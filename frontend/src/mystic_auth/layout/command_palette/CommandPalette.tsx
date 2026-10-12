import React, { useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../ui/shadcn/dialog";
import { SEARCH_QUERY_MAX_LENGTH } from "../../ui/styles/inputStyles";
import { type NavItem } from "../app_layout/navItems";
import { type SearchItem } from "./searchItems";
import { useDebouncedValue } from "../../ui/hooks/useDebouncedValue";
import { useCommandPaletteResults } from "./CommandPaletteResults";
import CommandPaletteResultsList from "./CommandPaletteResultsList";

interface CommandPaletteProps {
    isOpen: boolean;
    onClose: () => void;
    /** Appended after the built-in NAV_ITEMS - pass the same reference given
     * to AppLayout so the palette's "Pages" group matches the sidebar. */
    extraNavItems?: NavItem[];
    /** Appended after the built-in SEARCH_ITEMS - your own page's searchable
     * content (a settings card, a specific tab/section). */
    extraSearchItems?: SearchItem[];
}

/**
 * Cmd+K / Ctrl+K quick-jump palette: search/select any nav destination the
 * caller has permission to see (same gating as Sidebar, via
 * useAuthorization().can). Once the query is non-empty it also searches:
 *  - content within pages (SEARCH_ITEMS/searchItems.ts - a settings tab, an
 *    audit-log category/scope), so e.g. "password" surfaces "Change
 *    Password" even though it's not a nav item itself. Selecting one
 *    navigates to a `?query=param` a page reads on mount to pick a tab, or a
 *    `#hash` AppLayout's useScrollToHash scrolls to.
 *  - every matching string across all pages, Ctrl+F-style: each distinct
 *    string under a page's PAGE_CONTENT_NAMESPACES or a SEARCH_ITEMS'
 *    `scope` that contains the query becomes its own row, capped at
 *    TEXT_MATCH_RESULTS_LIMIT.
 *  - real policy records server-side, gated on policies:read. Selecting one
 *    jumps to /policies?search=<policy-name>, which PoliciesPage reads on entry.
 *  - real user accounts server-side (same endpoint UsersPage.tsx uses),
 *    gated on users:list_all. Selecting one jumps to
 *    /users?search=<email>, which UsersPage reads on mount to pre-filter.
 * Controlled by App.tsx, which owns the global keydown listener that toggles
 * `isOpen`. Result-building lives in CommandPaletteResults.ts, the list's
 * rendering in CommandPaletteResultsList.tsx - this file owns the dialog
 * shell, search input, and keyboard navigation.
 */
const CommandPalette: React.FC<CommandPaletteProps> = ({ isOpen, onClose, extraNavItems, extraSearchItems }) => {
    const { t } = useTranslation("layout");
    const navigate = useNavigate();

    const [query, setQuery] = useState("");
    const [activeIndex, setActiveIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const debouncedQuery = useDebouncedValue(query);
    const trimmedQuery = debouncedQuery.trim();

    const { filtered, kindCount } = useCommandPaletteResults(trimmedQuery, extraNavItems, extraSearchItems);

    // Reset search + selection every time the palette opens, so it never
    // reopens showing the previous session's leftover query/highlight.
    // Adjusted during render (same pattern as PolicyFormDialog/
    // UserPoliciesDialog) rather than in an effect, to avoid an extra render.
    const [prevIsOpen, setPrevIsOpen] = useState(isOpen);
    if (isOpen !== prevIsOpen) {
        setPrevIsOpen(isOpen);
        if (isOpen) {
            setQuery("");
            setActiveIndex(0);
        }
    }

    // Same reasoning: snap the highlight back to the top result as the query
    // changes, computed during render rather than via a `[query]` effect.
    const [prevQuery, setPrevQuery] = useState(query);
    if (query !== prevQuery) {
        setPrevQuery(query);
        setActiveIndex(0);
    }

    const goTo = (to: string) => {
        navigate(to);
        onClose();
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setActiveIndex((i) => (filtered.length === 0 ? 0 : (i + 1) % filtered.length));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActiveIndex((i) => (filtered.length === 0 ? 0 : (i - 1 + filtered.length) % filtered.length));
        } else if (e.key === "Enter") {
            e.preventDefault();
            const target = filtered[activeIndex];
            if (target) goTo(target.to);
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent
                showCloseButton={false}
                overlayClassName="backdrop-blur-[2px]"
                // DialogContent's full-screen flex wrapper centers this panel
                // vertically and horizontally. Avoid positional offsets here
                // so the command palette remains centered at every viewport
                // size.
                className="max-w-md border-brand-border rounded-card bg-bg-surface p-0 shadow-dialog overflow-hidden"
                // Focuses the search input specifically, not whatever Radix's
                // default open-autofocus would pick (the first focusable
                // element happens to already be this input, but pin it
                // explicitly - matches the old Dialog.Root's initialFocusEl).
                onOpenAutoFocus={(e) => {
                    e.preventDefault();
                    inputRef.current?.focus();
                }}
            >
                {/* Radix's Dialog requires an explicit Title/Description for
                    an accessible name/description - sr-only, since the visible search input
                    already carries its own aria-label and this dialog has no
                    visible heading in the design. */}
                <DialogTitle className="sr-only">{t("commandPalette.placeholder")}</DialogTitle>
                <DialogDescription className="sr-only">{t("commandPalette.placeholder")}</DialogDescription>
                <div className="flex items-center gap-2 border-b border-brand-border px-4 py-3">
                    <div className="text-fg-muted shrink-0">
                        <Search size={18} aria-hidden="true" />
                    </div>
                    {/* Bare input, not ui/inputs/Input.tsx: this is a borderless
                        "flushed" field, not the app's usual bordered look.
                        The header divider provides the same visual separation
                        used below dialog titles without attaching an underline
                        directly to the focused text field. */}
                    <input
                        ref={inputRef}
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        maxLength={SEARCH_QUERY_MAX_LENGTH}
                        placeholder={t("commandPalette.placeholder")}
                        className="flex-1 min-w-0 bg-transparent outline-none text-base md:text-sm placeholder:text-muted-foreground"
                        autoComplete="off"
                        aria-label={t("commandPalette.placeholder")}
                    />
                    {/* height 1.25rem, subtle/gray variant - see
                        Navbar.tsx's matching comment. */}
                    <kbd className="hidden sm:inline-flex items-center shrink-0 whitespace-nowrap select-none font-medium text-sm h-5 px-1 rounded-md bg-gray-200 text-gray-800 dark:bg-gray-800 dark:text-gray-200">Esc</kbd>
                </div>

                <div className="flex flex-col gap-0 py-2 max-h-80 overflow-y-auto">
                    <CommandPaletteResultsList
                        filtered={filtered}
                        kindCount={kindCount}
                        activeIndex={activeIndex}
                        setActiveIndex={setActiveIndex}
                        goTo={goTo}
                    />
                </div>
            </DialogContent>
        </Dialog>
    );
};

export default CommandPalette;
