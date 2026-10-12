import React from "react";
import { CalendarDays, Clock, KeyRound, Mail, Monitor, ShieldCheck, Sun, UserX } from "lucide-react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";

import AppTooltip from "../ui/feedback/AppTooltip";
import Badge from "../ui/badges/Badge";
import { Button } from "../ui/buttons/Button";
import { cn } from "../ui/styles/classNames";
import { initialsFor } from "../layout/app_layout/initialsFor";
import DashboardIdentityCardSkeleton from "./DashboardIdentityCardSkeleton";
import DashboardStatItem from "./DashboardStatItem";
import FormAlert from "../ui/feedback/FormAlert";
import { formatMemberSince, formatTimeOnly } from "../ui/dates/dateFormatters";
import { parseUserAgent } from "../active_sessions/parseUserAgent";
import type { SupportedLanguage } from "../translations/translations";
import type { CurrentUserProfile } from "../auth/current_user/current_user_types";
import type { PreviousLogin } from "./usePreviousLoginQuery";

/** Rest state matches design/dashboard.html's `.btn-ghost`: a neutral
 * bg.surface/border.strong/fg.muted button, not brand-tinted at rest - only
 * turning brand-colored (bg.brand-subtle/border.brand-solid/fg.brand) on
 * hover. TableActionButton's "brand" palette (tried first) is tinted even at
 * rest, which read as too prominent for what are secondary shortcuts next to
 * the page's real primary actions. border.strong (not border.default,
 * used before): `.btn-ghost{border-color:var(--border-strong)}` in the
 * mockup - border.default is a darker, differently-toned gray tuned for
 * form-input visibility instead. */
const NEUTRAL_HOVER_BRAND_BUTTON_CLASSNAME =
    "font-medium bg-bg-surface border-border-strong text-fg-muted hover:bg-brand-subtle hover:border-brand-solid hover:text-brand-fg";

// Layout follows the card's own width (Tailwind v4 named container
// queries), not the window's, so it stays correct wherever the card is
// placed, including next to the sidebar in a narrow window. Thresholds are
// arbitrary rem values so they move with the font size toggle, same as the
// old CSS-in-JS "@container identity (min-width: Xrem)" queries this
// replaces.
const ROOT_CLASSNAME = "relative @container/identity";

/** Identity block and shortcut buttons: one row when the card is wide enough
 * for both, otherwise buttons wrap below the identity block. */
const HEADER_CLASSNAME =
    "flex flex-col items-stretch gap-4 @min-[50rem]/identity:flex-row @min-[50rem]/identity:items-center @min-[50rem]/identity:justify-between @min-[50rem]/identity:gap-5";

const BUTTONS_CLASSNAME = "flex flex-wrap gap-2 @min-[50rem]/identity:flex-nowrap @min-[50rem]/identity:shrink-0";

/** Three stats spread evenly with divider lines between them
 * (design/dashboard.html's .stat-strip) when there's room; stacked without
 * dividers otherwise, where a left border would read as a stray line. */
const STATS_CLASSNAME = "flex flex-col gap-4 @min-[36rem]/identity:flex-row @min-[36rem]/identity:gap-0";
const STAT_ITEM_CLASSNAME = "flex-1 min-w-0";
/** Applied to every stat item after the first, once the row layout kicks in
 * (see STATS_CLASSNAME) - border-s (not border-l), same logical-property
 * reasoning as the original borderInlineStartWidth, so the divider stays on
 * the correct side in an RTL layout. */
const STAT_DIVIDER_CLASSNAME = "@min-[36rem]/identity:ps-5 @min-[36rem]/identity:border-s @min-[36rem]/identity:border-border-card";

interface DashboardIdentityCardProps {
    user: CurrentUserProfile | undefined;
    isLoading: boolean;
    isError: boolean;
    /** undefined while loading, null when there's no login before this one. */
    previousLogin: PreviousLogin | null | undefined;
    language: SupportedLanguage;
    onActiveSessionsClick: () => void;
}

/**
 * DashboardIdentityCard
 * ----------------------------
 * The identity strip at the top of DashboardPage: avatar/name/role/email plus
 * two shortcut buttons (Change Password, Appearance), then
 * three stats (Member Since/Previous Login/Active Sessions) below a divider.
 * Active Sessions jumps to ActiveSessionsCard further down the page.
 *
 * No Logout All button here: it lives on ActiveSessionsCard next to the
 * rest of session management. See DashboardPage.tsx for how
 * `user`/`previousLogin` are sourced.
 */
const DashboardIdentityCard: React.FC<DashboardIdentityCardProps> = ({
    user,
    isLoading,
    isError,
    previousLogin,
    language,
    onActiveSessionsClick,
}) => {
    const { t } = useTranslation("dashboard");
    const navigate = useNavigate();

    if (isLoading) return <DashboardIdentityCardSkeleton loadingLabel={t("loadingDetails")} />;
    if (isError) return <div><FormAlert status="error">{t("unableToFetch")}</FormAlert></div>;
    if (!user) {
        // Plain divs, not a compound EmptyState component: this is just an
        // icon-badge + title layout, not an interactive primitive needing
        // its own Radix wrapper (unlike Tabs/Select/Dialog).
        return (
            <div className="flex flex-col items-center text-center gap-4 py-8">
                <div className="w-16 h-16 flex items-center justify-center rounded-full bg-accent-subtle text-accent-fg border border-accent-border">
                    <UserX size={32} aria-hidden="true" />
                </div>
                <p className="text-lg font-semibold">{t("noUserData")}</p>
            </div>
        );
    }

    let previousLoginValue: React.ReactNode = "-";
    if (previousLogin === null) {
        previousLoginValue = (
            <span className="font-medium text-fg-muted">
                {t("noPreviousLogin")}
            </span>
        );
    } else if (previousLogin) {
        const device = parseUserAgent(previousLogin.user_agent);
        // The device shows as a second line (not hover-only), since it's the
        // detail that makes someone notice a login that wasn't theirs. The
        // IP stays in the tooltip to keep the stat compact.
        previousLoginValue = (
            <AppTooltip content={previousLogin.ip_address ? `${device} · ${previousLogin.ip_address}` : device}>
                <div className="min-w-0">
                    <div>
                        {formatMemberSince(previousLogin.created_at, language)}
                        <span className="font-medium text-fg-muted">
                            {" "}
                            {formatTimeOnly(previousLogin.created_at, language)}
                        </span>
                    </div>
                    <p className="text-xs font-normal text-fg-muted truncate">
                        {device}
                    </p>
                </div>
            </AppTooltip>
        );
    }

    return (
        <div className={ROOT_CLASSNAME}>
            <div className={HEADER_CLASSNAME}>
                <div className="flex items-center gap-4 flex-[0_1_auto] min-w-0">
                    <div className="w-14 h-14 shrink-0 rounded-2xl bg-brand-solid flex items-center justify-center text-brand-contrast text-lg font-bold">
                        {initialsFor(user.name, user.email)}
                    </div>

                    <div className="min-w-0 flex-1">
                        {/* Name and role badge both truncate, so a long name
                            or custom role label can't grow the block past the
                            card. The role badge gives way first. */}
                        <div className="flex items-center gap-2 min-w-0">
                            <AppTooltip content={user.name}>
                                <h2 className="text-xl font-bold flex-[0_1_auto] min-w-20 max-w-full truncate">
                                    {user.name}
                                </h2>
                            </AppTooltip>
                            <AppTooltip content={user.role ?? t("noRole")}>
                                <Badge
                                    colorPalette={user.role ? "brand" : "gray"}
                                    variant="subtle"
                                    className="px-2 py-0.5 text-xs font-bold rounded-full capitalize inline-flex items-center gap-1 shrink max-w-36 min-w-12 overflow-hidden"
                                >
                                    <ShieldCheck size={12} aria-hidden="true" style={{ flexShrink: 0 }} />
                                    <span className="truncate">{user.role ?? t("noRole")}</span>
                                </Badge>
                            </AppTooltip>
                        </div>
                        <div className="flex items-center gap-2 text-fg-muted mt-1 min-w-0">
                            <Mail size={16} aria-hidden="true" style={{ flexShrink: 0 }} />
                            <AppTooltip content={user.email}>
                                <p className="text-sm flex-[0_1_auto] min-w-0 max-w-full truncate">
                                    {user.email}
                                </p>
                            </AppTooltip>
                        </div>
                    </div>
                </div>

                <div className={BUTTONS_CLASSNAME}>
                    <Button size="sm" variant="outline" className={`text-sm ${NEUTRAL_HOVER_BRAND_BUTTON_CLASSNAME}`} onClick={() => navigate("/account-settings?tab=password")}>
                        <KeyRound size={13} aria-hidden="true" /> {t("quickLinks.changePassword")}
                    </Button>
                    <Button size="sm" variant="outline" className={`text-sm ${NEUTRAL_HOVER_BRAND_BUTTON_CLASSNAME}`} onClick={() => navigate("/account-settings?tab=appearance")}>
                        <Sun size={13} aria-hidden="true" /> {t("quickLinks.appearance")}
                    </Button>
                </div>
            </div>

            <div className={cn(STATS_CLASSNAME, "mt-5 pt-5 border-t border-border-card")}>
                <div className={STAT_ITEM_CLASSNAME}>
                    <DashboardStatItem
                        icon={<CalendarDays size={20} aria-hidden="true" />}
                        label={t("memberSince")}
                        value={formatMemberSince(user.created_at, language)}
                    />
                </div>
                <div className={cn(STAT_ITEM_CLASSNAME, STAT_DIVIDER_CLASSNAME)}>
                    <DashboardStatItem icon={<Clock size={20} aria-hidden="true" />} label={t("previousLogin")} value={previousLoginValue} />
                </div>
                <div className={cn(STAT_ITEM_CLASSNAME, STAT_DIVIDER_CLASSNAME)}>
                    <DashboardStatItem
                        icon={<Monitor size={20} aria-hidden="true" />}
                        label={user.active_sessions === 1 ? t("activeSession") : t("activeSessions")}
                        value={user.active_sessions}
                        onClick={onActiveSessionsClick}
                        actionLabel={t("goToActiveSessions", { count: user.active_sessions })}
                    />
                </div>
            </div>
        </div>
    );
};

export default DashboardIdentityCard;
