import React from "react";
import { Menu, Search } from "lucide-react";

import { useAuthStore } from "../../store/authStore";
import { useLanguageStore } from "../../store/languageStore";
import AppTooltip from "../../ui/feedback/AppTooltip";
import translations from "../../translations/translations";
import LogoutButton from "../../auth/logout/LogoutButton";
import ControlCluster from "../controls/ControlCluster";
import { Button } from "../../ui/buttons/Button";
import { cn } from "../../ui/styles/classNames";
import { initialsFor } from "./initialsFor";

interface NavbarProps {
    onToggleSidebar: () => void;
    /**
     * App-supplied content rendered in the top bar's action cluster, left of
     * ThemeToggle/LogoutButton. A free-form ReactNode (unlike Sidebar's
     * `extraItems` list) since the built-ins here are each bespoke
     * components. Optional, defaults to none.
     */
    extraContent?: React.ReactNode;
    /**
     * Opens the Cmd+K/Ctrl+K command palette, giving it a visible clickable
     * trigger alongside the keyboard shortcut. Optional: omitting it hides
     * the trigger.
     */
    onOpenCommandPalette?: () => void;
}

/** Top bar shown alongside Sidebar: mobile menu toggle, signed-in user, logout. */
const Navbar: React.FC<NavbarProps> = ({ onToggleSidebar, extraContent, onOpenCommandPalette }) => {
    // Chrome (navbar + Sidebar) renders in chromeLanguage, not the page-wide
    // translation language. See store/languageStore.ts's LanguageMode docstring.
    const chromeLanguage = useLanguageStore((s) => s.chromeLanguage);
    useLanguageStore((s) => s.languageRevision);
    const t = translations.getFixedT(chromeLanguage, "layout");
    const name = useAuthStore((s) => s.name);
    const email = useAuthStore((s) => s.email);
    const initials = initialsFor(name, email);

    return (
        <header
            className={cn(
                "flex items-center justify-between gap-y-2 px-4 md:px-6 py-2 md:py-0 h-auto md:h-16 min-h-16 shrink-0",
                // Below md, the action cluster doesn't fit next to the menu
                // toggle/greeting in one row, so wrap to a second line instead of
                // forcing horizontal scroll. md+ stays a single fixed-height row,
                // lined up with Sidebar's border-bottom.
                "flex-wrap md:flex-nowrap",
                // bg-bg-sidebar, not bg-bg-surface: matches Sidebar.tsx's panel
                // tone (design/dashboard.html's --bg-chrome, a faint warm tint -
                // not flat white/near-black) so the two chrome surfaces read as
                // one cohesive frame around the page, rather than the navbar
                // looking like just another card.
                "bg-bg-sidebar border-b border-border-strong sticky top-0 z-[1100]"
            )}
        >
            <div className="flex items-center gap-3 min-w-0">
                <Button
                    aria-label={t("toggleNavigationMenu")}
                    onClick={onToggleSidebar}
                    className="inline-flex md:hidden"
                    variant="icon"
                    size="icon-sm"
                >
                    <Menu size={16} aria-hidden="true" />
                </Button>
                {name && (
                    <div className="flex items-center gap-2.5 min-w-0">
                        {/* design/dashboard.html's `.avatar-sm`: a soft
                            brand-tinted badge (brand-100/brand-600 light,
                            translucent brand wash/#e8926f dark), not a solid
                            brand.solid fill - that's DashboardIdentityCard's
                            bigger `.avatar-lg`, a deliberately different,
                            fully-filled gradient treatment. This smaller
                            navbar avatar previously reused the solid
                            treatment, reading noticeably bolder/heavier than
                            the mockup's subtle topbar badge. */}
                        <div
                            className="w-8 h-8 shrink-0 rounded-full border border-[var(--brand-400)] bg-brand-subtle text-brand-fg flex items-center justify-center text-sm font-semibold"
                            aria-hidden="true"
                        >
                            {initials}
                        </div>
                        {/* Flex row (not inline text) so the name is the one item
                            that shrinks/truncates against however much space the
                            flex ancestors give it. "Signed in as" never shrinks or
                            wraps, since a wrapped line would overflow the
                            fixed-height (md+) navbar. */}
                        <div className="flex items-center gap-1 min-w-0">
                            {/* "sm", matching design/dashboard.html's
                                .topbar-left (14px, tightened from 16px). */}
                            <p className="text-sm text-fg-muted shrink-0 whitespace-nowrap">
                                {t("signedInAs")}
                            </p>
                            <AppTooltip content={name}>
                                <p className="text-sm font-semibold text-fg-default flex-[1_1_auto] min-w-0 max-w-full truncate">
                                    {name}
                                </p>
                            </AppTooltip>
                        </div>
                    </div>
                )}
            </div>

            {/* shrink (CSS default) plus min-w-0 (overrides flex's default
                min-width:auto) let this box actually shrink below its 556px
                natural width, so flex-wrap below has room to wrap its
                children onto a second line instead of forcing horizontal
                overflow. No visible effect on desktop, where it all fits on
                one line anyway. */}
            <div className="flex items-center gap-3 flex-wrap justify-end gap-y-2 shrink min-w-0">
                {extraContent}
                {onOpenCommandPalette && (
                    // A button styled like a search field, not a real Input:
                    // typing here does nothing, it just opens the dialog.
                    // Hidden below md; the keyboard shortcut still works there.
                    <button
                        type="button"
                        onClick={onOpenCommandPalette}
                        aria-label={t("commandPalette.triggerLabel")}
                        className={cn(
                            "hidden md:flex items-center gap-2 w-56 h-9 px-3 rounded-control border border-border-strong bg-bg-canvas text-fg-muted cursor-pointer",
                            "transition-[background-color,border-color,color] duration-[var(--duration-hover)] ease-[var(--easing-hover)]",
                            // Matches design/dashboard.html's own
                            // `.search-box:hover` (brand-tinted border+fill),
                            // same brand-bold treatment Button's "icon" variant
                            // uses - a previous neutral-gray-only hover here read
                            // as a barely-there cue next to the icon-button
                            // cluster right beside it.
                            "hover:border-[var(--brand-500)] hover:bg-[var(--brand-100)] hover:text-[var(--brand-700)]",
                            "dark:hover:border-[var(--brand-400)] dark:hover:bg-[color-mix(in_srgb,var(--brand-solid)_16%,transparent)] dark:hover:text-brand-fg"
                        )}
                    >
                        <Search size={15} aria-hidden="true" />
                        <span className="flex-1 text-left text-sm">
                            {t("commandPalette.trigger")}
                        </span>
                        {/* height 1.125rem, subtle/gray variant: matches the
                            rest of the app's "sm" kbd sizing. */}
                        <kbd className="inline-flex items-center shrink-0 whitespace-nowrap select-none font-medium text-xs h-[1.125rem] px-1 rounded-md bg-gray-200 text-gray-800 dark:bg-gray-800 dark:text-gray-200">⌘K</kbd>
                    </button>
                )}
                <ControlCluster />
                <LogoutButton />
            </div>
        </header>
    );
};

export default Navbar;
