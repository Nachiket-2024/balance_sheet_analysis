import React, { useState } from "react";
import { Link, NavLink } from "react-router";
import { Mail, type LucideIcon } from "lucide-react";

import { IfCan } from "../../authorization/IfCan";
import { NAV_ITEMS, type NavItem } from "./navItems";
import Logo from "./Logo";
import { useLanguageStore } from "../../store/languageStore";
import { useThemeStore } from "../../store/themeStore";
import translations from "../../translations/translations";
import { prefetchRoute } from "./routePrefetch";
import { SUPPORT_EMAIL } from "../../core/settings";
import { cn } from "../../ui/styles/classNames";

// Same value as themeTokens.ts's durations.hover/easings.hover, composed as
// a literal transition string for these plain-inline-style call sites
// (NavLink's `style` prop takes an object, not Tailwind classes).
const FAST_HOVER_TRANSITION = ["background-color", "border-color", "color"]
    .map((property) => `${property} var(--duration-hover) var(--easing-hover)`)
    .join(", ");

interface SidebarProps {
    isOpen: boolean;
    onNavigate: () => void;
    /**
     * App-supplied links, merged with the built-in ones and sorted by
     * `order` (items without one sort last, in the order given). Same
     * NavItem shape and IfCan gating as the built-ins. Optional, defaults to
     * none.
     */
    extraItems?: NavItem[];
}

interface SidebarNavLinkProps {
    to: string;
    onClick: () => void;
    label: string;
    icon?: LucideIcon;
}

/**
 * Single nav entry. Tracks hover in state rather than a CSS `:hover` rule,
 * since NavLink's `style` prop only takes a function of `{ isActive }` with
 * no hover equivalent.
 */
const SidebarNavLink: React.FC<SidebarNavLinkProps> = ({ to, onClick, label, icon: Icon }) => {
    const [isHovered, setIsHovered] = useState(false);
    const isDark = useThemeStore((s) => s.colorMode === "dark");

    // Copied directly from design/dashboard.html's own `.nav-item`/
    // `.nav-item:hover`/`.nav-item.active` rules rather than re-derived: a
    // translucent brand-500 wash at a handful of specific alphas (16%/22%
    // hover, 24%/34% active - light/dark), not a solid color step. A solid
    // brand.200/800/900 step lands on visibly different colors than the
    // mockup's actual translucent fills, and can't self-adjust the way an
    // alpha wash does when layered over bg.sidebar's own brand tint.
    // color-mix keeps this tied to the live brand.solid token (works for
    // any brand color a fork/Appearance picks), same reasoning as
    // AppLayout's canvas glow. NavLink's style prop is a plain inline
    // style with no dark-mode variant syntax, hence reading colorMode
    // directly instead.
    const hoverBg = `color-mix(in srgb, var(--brand-solid) ${isDark ? 22 : 16}%, transparent)`;
    const activeBg = `color-mix(in srgb, var(--brand-solid) ${isDark ? 34 : 24}%, transparent)`;
    // brand.fg already resolves to the mockup's own active-text colors:
    // brand.700 light (measured against the mockup's `.nav-item.active`
    // color) / brand.300ish dark (the mockup's literal #e8926f is a step in
    // that same light-tinted range).
    const activeColor = "var(--brand-fg)";
    // Mockup's `.nav-item` is fg-muted at rest and only brightens to
    // fg-default on hover (`.nav-item:hover{color:var(--fg-default)}`) -
    // an inactive link was previously pinned to fg-default even at rest,
    // reading as full-strength text identical to the active item's weight.
    const inactiveColor = isHovered ? "var(--fg-default)" : "var(--fg-muted)";

    return (
        <NavLink
            to={to}
            className="mystic-sidebar-link"
            onClick={onClick}
            onMouseEnter={() => {
                setIsHovered(true);
                prefetchRoute(to);
            }}
            onMouseLeave={() => setIsHovered(false)}
            onFocus={() => prefetchRoute(to)}
            style={({ isActive }) => ({
                display: "block",
                // Plain padding, no border-left reservation: the mockup's
                // `.nav-item.active` has no left-border indicator at all
                // (an earlier version added one) - background/color/
                // font-weight alone mark the active item, matching
                // design/dashboard.html exactly.
                // 0.75rem/0.375rem: Tailwind's own p-3/rounded-md values -
                // literal, not a var, since Tailwind v4 only exposes a
                // spacing/radius step as a CSS custom property for steps
                // this app defines itself (--radius-card/--radius-control
                // above), not for its own built-in scale.
                padding: "0.625rem 0.75rem",
                borderRadius: "0.375rem",
                // 15px, a step above the app's 14px body text: nav items are
                // primary navigation used on every page, not secondary/
                // supporting copy, so matching body text exactly flattened
                // that hierarchy. An earlier pass went to 17px and read too
                // large next to the rest of the chrome; 15px keeps it a
                // deliberate step up without that.
                fontSize: "15px",
                fontWeight: isActive ? 600 : 500,
                color: isActive ? activeColor : inactiveColor,
                background: isActive ? activeBg : isHovered ? hoverBg : "transparent",
                // A ~200ms transition reads as sluggish for hover feedback,
                // hence the faster FAST_HOVER_TRANSITION here.
                transition: FAST_HOVER_TRANSITION,
            })}
        >
            {({ isActive }) => (
                <div className="flex items-center gap-2.5">
                    {Icon && (
                        <Icon
                            size={17}
                            aria-hidden="true"
                            color={isActive ? activeColor : inactiveColor}
                            style={{ flexShrink: 0, transition: FAST_HOVER_TRANSITION }}
                        />
                    )}
                    <span>{label}</span>
                </div>
            )}
        </NavLink>
    );
};

/**
 * Primary app navigation. Always visible on md+ screens; on smaller screens
 * it's an off-canvas panel toggled by Navbar's menu button (slides via
 * transform, staying in the DOM). Permission-gated links are wrapped in
 * IfCan; the route itself is still independently enforced by ProtectedRoute.
 */
const Sidebar: React.FC<SidebarProps> = ({ isOpen, onNavigate, extraItems }) => {
    // Chrome (sidebar + Navbar) renders in chromeLanguage, not the page-wide
    // translation language. See store/languageStore.ts's LanguageMode docstring.
    const chromeLanguage = useLanguageStore((s) => s.chromeLanguage);
    useLanguageStore((s) => s.languageRevision);
    const t = translations.getFixedT(chromeLanguage, "layout");
    // Built-in items pass a "namespace:key" translation key; app-supplied
    // extraItems pass a plain display string. exists() tells them apart.
    const resolveLabel = (label: string): string => (translations.exists(label, { lng: chromeLanguage }) ? t(label) : label);
    // Array.sort is stable, so items with the same (or missing) order keep
    // their relative position. Missing order falls back to Infinity, not
    // undefined, since undefined - undefined is NaN, not 0.
    const items = extraItems && extraItems.length > 0
        ? [...NAV_ITEMS, ...extraItems].sort(
              (a, b) => (a.order ?? Infinity) - (b.order ?? Infinity)
          )
        : NAV_ITEMS;
    return (
        // NavLink's `style` prop can't express :focus-visible, so
        // .mystic-sidebar-link:focus-visible in theme/tailwind.css gives
        // this link the same brand-colored focus ring other focusable
        // controls get from their recipe - a real stylesheet rule now,
        // not a runtime-injected <style> tag (a strict hash-only CSP
        // can't allow one; see that file for the full rationale).
        <nav
            aria-label={t("mainNavigation")}
            className={cn(
                // 13.875rem (222px), matching design/dashboard.html's own
                // `.sidebar{width:222px}` exactly - narrow enough of a gap
                // from a round number to go unnoticed prop-by-prop, but
                // visible side-by-side against the mockup.
                "fixed md:sticky top-0 left-0 h-screen w-[13.875rem] shrink-0 bg-bg-sidebar border-r border-border-strong z-[1300] flex flex-col",
                // md:translate-x-0 unconditionally (not just an override):
                // this is a plain className, not fighting an inline style,
                // so the off-canvas transform only ever applies below md.
                "transition-transform duration-[var(--duration-base)] ease-[var(--easing-hover)] md:translate-x-0",
                isOpen ? "translate-x-0" : "-translate-x-full"
            )}
        >
            {/* h-16: no border here (design/dashboard.html's `.brand-row`
                has none - a previous border-bottom "to line up with
                Navbar's own" didn't actually exist in the mockup and read
                as a stray line under the logo that design doesn't have).
                The fixed height still keeps this row visually level with
                Navbar's own 64px bar, without needing a border to do it. */}
            <div className="h-16 px-6 flex items-center shrink-0">
                <Link to="/dashboard" onClick={onNavigate} style={{ textDecoration: "none" }}>
                    <Logo size="sm" />
                </Link>
            </div>

            {/* gap-0, not a positive gap: design/dashboard.html's
                `.nav-item` already carries its own 10px vertical padding as
                the only spacing between items - an extra gap on top of that
                padding was stacking two spacing sources, reading as visibly
                airier than the mockup. overflow-y-auto (not in the mockup,
                which only ever shows 3 items) so a fork that adds many more
                nav items scrolls this list independently instead of
                overflowing past the pinned footer below. */}
            <div
                className="flex flex-col p-3 gap-0 overflow-y-auto flex-[1_1_auto] min-h-0"
                data-testid="nav-links"
            >
                {items.map((item) => {
                    const link = (
                        <SidebarNavLink
                            key={item.to}
                            to={item.to}
                            onClick={onNavigate}
                            label={resolveLabel(item.label)}
                            icon={item.icon}
                        />
                    );

                    if (!item.permission) return link;

                    return (
                        <IfCan key={item.to} action={item.permission}>
                            {link}
                        </IfCan>
                    );
                })}
            </div>

            {/* Pinned to the bottom rather than mixed into the nav list: a
                support contact isn't a page to navigate to. Only renders once
                SUPPORT_EMAIL is configured (unset by default, core/settings.ts)
                so a fresh fork doesn't show a link to nothing. Also duplicated
                as a card on Account Settings' Legal tab. */}
            {SUPPORT_EMAIL && (
                // border-border-card (design's plain --border), not
                // border-strong - matches
                // `.sidebar-footer{border-top:1px solid var(--border)}`, one
                // step fainter than the sidebar's own outer edge.
                <div className="p-3 mt-auto border-t border-border-card shrink-0">
                    <a
                        href={`mailto:${SUPPORT_EMAIL}`}
                        className="flex items-center gap-2.5 px-3 py-2 rounded-control text-sm font-semibold text-brand-fg no-underline hover:bg-brand-subtle hover:underline"
                        style={{ transition: FAST_HOVER_TRANSITION }}
                    >
                        <Mail size={17} aria-hidden="true" style={{ flexShrink: 0 }} />
                        {t("footer.help")}
                    </a>
                </div>
            )}
        </nav>
    );
};

export default Sidebar;
