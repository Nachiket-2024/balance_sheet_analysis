import React from "react";
import { useTranslation } from "react-i18next";
import { LayoutDashboard } from "lucide-react";

// Reuses the same TanStack Query cache entry useAuthSession() (called once
// at the app root) already populates, so this page skips a duplicate
// GET /auth/me call and its own loading/error state.
import { useCurrentUserQuery } from "../auth/current_user/useCurrentUserQuery";
import { usePreviousLoginQuery } from "./usePreviousLoginQuery";
import { useLanguageStore } from "../store/languageStore";
import { useNow } from "../ui/hooks/useNow";
import { formatLongDate } from "../ui/dates/dateFormatters";

import Card from "../ui/cards/Card";
import DashboardIdentityCard from "./DashboardIdentityCard";
import OperationsShortcutsCard from "./OperationsShortcutsCard";
import ActiveSessionsCard from "../active_sessions/ActiveSessionsCard";

/** DOM id of ActiveSessionsCard on this page, the target of the identity
 * card's clickable Active sessions stat. */
export const ACTIVE_SESSIONS_SECTION_ID = "active-sessions";

/** Scrolls to the sessions card and moves focus there, so keyboard and
 * screen reader users land in the same place sighted users see. Honors
 * prefers-reduced-motion. */
function goToActiveSessions() {
    const section = document.getElementById(ACTIVE_SESSIONS_SECTION_ID);
    if (!section) return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    // Focus first: focusing after a smooth scroll has started cancels the
    // scroll in Chromium, even with preventScroll.
    section.focus({ preventScroll: true });
    section.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
}

/** Greeting by local hour: morning 5-11, afternoon 12-16, evening otherwise. */
function greetingKeyFor(hour: number): "morning" | "afternoon" | "evening" {
    if (hour >= 5 && hour < 12) return "morning";
    if (hour >= 12 && hour < 17) return "afternoon";
    return "evening";
}

/** How often the greeting and date re-check the clock, so a tab left open
 * across noon or midnight doesn't keep the old greeting or date. */
const GREETING_REFRESH_MS = 60_000;

/**
 * DashboardPage
 * ----------------------------
 * Displays the current user's information. Reads the current user from the
 * shared useCurrentUserQuery cache instead of fetching independently, so it
 * stays in sync with the rest of the app. ActiveSessionsCard (the full
 * sessions table, including "Log out everywhere"/bulk "Log out selected")
 * renders directly here as the sole place to manage sessions.
 *
 * Three full-width cards, stacked: identity, OperationsShortcutsCard (shortcut
 * tiles, each independently gated on one fine-grained PBAC permission -
 * absent entirely for a viewer holding none of them), and
 * ActiveSessionsCard. Kept stacked on wide screens too: side by side, the
 * Management tiles squeeze into a 2x2 grid, which reads worse than one
 * row. No login-trend chart here - that lives on the Security Log page.
 *
 * Own bare title/description (not PageContainer, which pairs its heading
 * with an `icon`/`actions` row this page has no use for), with the same
 * maxW="page.content" width cap. This is the page's only h1;
 * DashboardIdentityCard's name heading below is an h2.
 */
const DashboardPage: React.FC = () => {
    const { t } = useTranslation("dashboard");
    // See AllAuthorizationLogSection.tsx's matching comment: dates use
    // chromeLanguage, not pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const { data: user, isLoading, isError } = useCurrentUserQuery();
    const { data: previousLogin } = usePreviousLoginQuery();

    // Subtitle: a greeting with the user's first name plus today's date, in
    // place of a generic description. The h1 stays "Dashboard" so it matches
    // the sidebar entry and every other page's title. Until the user loads
    // (or if the name is blank), just the date.
    const now = useNow(GREETING_REFRESH_MS);
    const firstName = user?.name?.trim().split(/\s+/)[0];
    const today = formatLongDate(now, language);
    const subtitle = firstName ? `${t(`greeting.${greetingKeyFor(new Date(now).getHours())}`, { name: firstName })} · ${today}` : today;

    return (
        <div className="max-w-(--size-page-content) w-full">
            <div className="mb-6">
                {/* Same title/description text style PageContainer.tsx uses
                    (22px/1.2/bold/-0.01em and 14.5px/1.4) - this page skips
                    PageContainer itself (see docstring) so it sets these
                    directly, but the values must stay identical. */}
                <div className="flex items-center gap-2.5">
                    <LayoutDashboard size={22} aria-hidden="true" className="text-fg-muted" />
                    <h1 className="text-[24px] leading-[1.15] font-bold tracking-[-0.025em]">
                        {t("pageTitle")}
                    </h1>
                </div>
                <p className="text-fg-muted text-[14.5px] leading-[1.4] mt-1">
                    {subtitle}
                </p>
            </div>

            <div className="flex flex-col gap-5">
                {/* Brand accent bar on top: the one card on the page that
                    gets it, marking it as "your own identity" versus the
                    system-wide cards below. */}
                <Card className="relative overflow-hidden p-5 text-fg-default border-t-[3px] border-t-brand-solid shadow-card hover:shadow-card-hover">
                    <div
                        aria-hidden="true"
                        className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-[linear-gradient(to_bottom,color-mix(in_srgb,var(--brand-solid)_14%,transparent),transparent_85%)]"
                    />
                    <DashboardIdentityCard
                        user={user}
                        isLoading={isLoading}
                        isError={isError}
                        previousLogin={previousLogin}
                        language={language}
                        onActiveSessionsClick={goToActiveSessions}
                    />
                </Card>

                {!isLoading && !isError && user && (
                    <>
                        <OperationsShortcutsCard />
                        {/* tabIndex -1 makes the card a focus target for
                            goToActiveSessions without adding it to the tab
                            order. scrollMarginTop keeps its heading clear of
                            the sticky navbar, which wraps to two rows in
                            narrow windows. */}
                        <ActiveSessionsCard
                            id={ACTIVE_SESSIONS_SECTION_ID}
                            tabIndex={-1}
                            className="scroll-mt-30 md:scroll-mt-20 outline-none"
                        />
                    </>
                )}
            </div>
        </div>
    );
};

export default DashboardPage;
