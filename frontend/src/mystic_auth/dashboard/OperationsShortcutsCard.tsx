import React from "react";
import { ChevronRight, Gauge, KeyRound, LayoutGrid, Shield, ShieldCheck, Users } from "lucide-react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import AppTooltip from "../ui/feedback/AppTooltip";
import Card from "../ui/cards/Card";
import SectionHeading from "../ui/navigation/SectionHeading";
import { cn } from "../ui/styles/classNames";
import { useCan } from "../authorization/useCan";
import { PERMISSIONS } from "../authorization/permissions";
import { useLanguageStore } from "../store/languageStore";
import { formatNumber } from "../translations/numerals";
import { useUserStatsQuery } from "../users/queries/userQueries";
import { usePoliciesQuery } from "../policies/queries/policyQueries";
import { usePermissionCatalogQuery } from "../policies/queries/permissionQueries";
import { listRateLimitsApi } from "../api/rate_limits_api";

// Tiles size themselves from the grid's width (Tailwind v4 named container
// queries), not the window's. Below 66rem (about a 1440px window with the
// sidebar) they switch to a compact style so all five still fit on one row
// at 1280-1366px. At 66rem and up, five regular 12.5rem tiles always fit.
// rem-based, so with a larger font size setting the grid wraps instead of
// overflowing.
const WIDE = "@min-[66rem]/admin";

const GRID_CONTAINER_CLASSNAME = "@container/admin";

// auto-fit (not auto-fill): with fewer permission-gated tiles, the
// remaining ones stretch to fill the row instead of leaving empty tracks.
const GRID_CLASSNAME = `grid gap-3 grid-cols-[repeat(auto-fit,minmax(10.5rem,1fr))] ${WIDE}:grid-cols-[repeat(auto-fit,minmax(12.5rem,1fr))]`;

const TILE_CLASSNAME = `p-3 gap-2 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${WIDE}:p-3.5 ${WIDE}:gap-2.5`;
// Give the icon tile a little more breathing room than the original compact
// treatment without making it as large as the full stat-card tiles.
const TILE_ICON_CLASSNAME = "w-8 h-8 [&>svg]:size-3.5";
const TILE_LABEL_CLASSNAME = `tracking-normal ${WIDE}:tracking-[0.025em]`;
const TILE_CHEVRON_CLASSNAME = `[&>svg]:w-[0.9375rem] [&>svg]:h-[0.9375rem] ${WIDE}:[&>svg]:w-[1.0625rem] ${WIDE}:[&>svg]:h-[1.0625rem]`;
const TILE_VALUE_CLASSNAME = `text-[1.25rem] ${WIDE}:text-[1.5rem]`;
const TILE_CAPTION_CLASSNAME = `text-[0.8125rem] ${WIDE}:text-[0.875rem]`;

interface TileProps {
    icon: React.ReactNode;
    label: string;
    onClick: () => void;
    // Omitted for a plain link tile (Security Events, which has no single
    // meaningful count to show - a raw failed-login count reads as an
    // alarm even when it's just an ordinary mistyped password) - icon/
    // label/chevron only, plus `secondary` as a static caption instead of
    // a number line.
    value?: number;
    isLoading?: boolean;
    /** The count request failed: shows a dash and "Couldn't load" instead of
     * an empty tile that looks like it's still loading. */
    isError?: boolean;
    secondary?: string;
}

/** One shortcut tile. Every tile uses the user's brand color (left accent,
 * icon, hover fill) instead of a fixed hue per category: tiles are told apart
 * by icon and label, and the whole row follows the user's Appearance pick
 * like the rest of the app (see .project/design.md's color system). */
const OperationShortcutTile: React.FC<TileProps> = ({ icon, label, value, isLoading, isError, secondary, onClick }) => {
    const { t } = useTranslation("dashboard");
    const language = useLanguageStore((s) => s.chromeLanguage);
    const hasCount = value !== undefined || isLoading || isError;
    const caption = isError ? t("administration.loadError") : secondary;
    return (
        <button
            type="button"
            onClick={onClick}
            className={cn(
                "text-left cursor-pointer flex flex-col min-w-0 min-h-[6.25rem] rounded-[11px]",
                // flex-start, not space-between: a tile without a number
                // (Security Events) then starts its caption where the other
                // tiles' numbers start, instead of sinking to the bottom.
                "justify-start",
                // Neutral at rest with only a 3px brand left border; tints on
                // hover (design/dashboard.html's `.tile` / `.tile:hover`).
                "bg-bg-surface border border-border-strong border-l-[3px]",
                // brand.500, not brand.solid (600): 600 read too heavy for a
                // border next to the pale hover fill.
                "border-l-[var(--brand-500)]",
                TILE_CLASSNAME,
                "transition-[background-color,border-color,box-shadow,transform] duration-[var(--duration-fast)] ease-[var(--easing-hover)]",
                "hover:bg-brand-tile-subtle hover:border-[var(--brand-500)] hover:shadow-card-hover",
                "focus-visible:outline-2 focus-visible:outline-[var(--brand-500)] focus-visible:outline-offset-2"
            )}
        >
            <div className="flex justify-between gap-1.5 min-w-0 w-full">
                <div className="flex items-center gap-3 min-w-0">
                    <div
                        className={cn(
                            "rounded-control bg-brand-tile-subtle border border-[var(--brand-500)] text-brand-fg flex items-center justify-center shrink-0",
                            TILE_ICON_CLASSNAME
                        )}
                    >
                        {icon}
                    </div>
                    {/* Truncates (full label in the tooltip) rather than
                        wrapping, so every tile's number starts on the same
                        line. */}
                    <AppTooltip content={label}>
                        <p className={cn("text-xs font-bold uppercase text-fg-muted truncate", TILE_LABEL_CLASSNAME)}>
                            {label}
                        </p>
                    </AppTooltip>
                </div>
                <div className={cn("shrink-0 flex text-fg-muted", TILE_CHEVRON_CLASSNAME)}>
                    <ChevronRight aria-hidden="true" />
                </div>
            </div>
            {hasCount ? (
                <div>
                    <p className={cn("font-extrabold text-fg-default leading-none tabular-nums", TILE_VALUE_CLASSNAME)}>
                        {isLoading || isError ? "–" : formatNumber(value, language)}
                    </p>
                    <p className={cn("text-fg-muted mt-1", TILE_CAPTION_CLASSNAME)}>
                        {caption}
                    </p>
                </div>
            ) : (
                <p className={cn("text-fg-muted", TILE_CAPTION_CLASSNAME)}>
                    {caption}
                </p>
            )}
        </button>
    );
};

/**
 * OperationsShortcutsCard
 * ----------------------------
 * Shortcut tiles to the permission-protected areas (Users/Policies/Permissions/Rate Limits/
 * Security Events) the current viewer holds permission for - independently,
 * one fine-grained PBAC permission per tile (role metadata has no special
 * dashboard access; it is profile metadata only, see
 * backend/mystic_auth/authorization/permissions.py). A viewer holding none
 * of these five permissions sees no card at all.
 *
 * Each tile's query is only enabled once its gating permission is held, so
 * a viewer without e.g. rate_limits:read never fires GET /rate-limits/ just
 * because this card mounted. Tiles reuse the same list/catalog queries
 * their own pages use, plus a one-off count-only rate limits query
 * (pageSize 1: only the total is used). Security Events has no count of its
 * own - a raw failed-login number isn't a meaningful alert, and a first
 * wrong password is common - so it's a plain link tile with a caption.
 */
const OperationsShortcutsCard: React.FC = () => {
    const { t } = useTranslation("dashboard");
    const navigate = useNavigate();

    const canUsers = useCan(PERMISSIONS.USERS_LIST_ALL);
    const canPolicies = useCan(PERMISSIONS.POLICIES_READ);
    const canPermissions = useCan(PERMISSIONS.PERMISSIONS_READ);
    const canRateLimits = useCan(PERMISSIONS.RATE_LIMITS_READ);
    const canSecurityAudit = useCan(PERMISSIONS.SECURITY_AUDIT_READ);

    const userStats = useUserStatsQuery(canUsers);
    const policies = usePoliciesQuery(canPolicies);
    const permissionCatalog = usePermissionCatalogQuery(canPermissions);

    const rateLimits = useQuery({
        queryKey: ["rate-limits", "count"],
        queryFn: async () => (await listRateLimitsApi({ pageSize: 1 })).data.total,
        enabled: canRateLimits,
    });

    if (!canUsers && !canPolicies && !canPermissions && !canRateLimits && !canSecurityAudit) return null;

    const activePolicies = policies.data?.filter((p) => p.is_active).length;
    const resourceTypes = permissionCatalog.data
        ? new Set(permissionCatalog.data.map((entry) => entry.resource_type)).size
        : undefined;

    return (
        <Card className="hover:shadow-card-hover">
            <SectionHeading level="subsection" className="mb-4 flex items-center gap-2 border-b border-border-card pb-3">
                <LayoutGrid size={16} aria-hidden="true" color="var(--brand-solid)" />
                {t("administration.heading")}
            </SectionHeading>
            <div className={GRID_CONTAINER_CLASSNAME}>
                <div className={GRID_CLASSNAME}>
                    {canUsers && (
                        <OperationShortcutTile
                            icon={<Users size={13} aria-hidden="true" />}
                            label={t("administration.users.label")}
                            value={userStats.data?.total}
                            isLoading={userStats.isLoading}
                            isError={userStats.isError}
                            secondary={t("administration.users.secondary", {
                                unverified: userStats.data?.unverified ?? 0,
                                inactive: userStats.data?.inactive ?? 0,
                            })}
                            onClick={() => navigate("/users")}
                        />
                    )}
                    {canPolicies && (
                        <OperationShortcutTile
                            icon={<ShieldCheck size={13} aria-hidden="true" />}
                            label={t("administration.policies.label")}
                            value={policies.data?.length}
                            isLoading={policies.isLoading}
                            isError={policies.isError}
                            secondary={t("administration.policies.secondary", {
                                active: activePolicies ?? 0,
                                inactive: (policies.data?.length ?? 0) - (activePolicies ?? 0),
                            })}
                            onClick={() => navigate("/policies")}
                        />
                    )}
                    {canPermissions && (
                        <OperationShortcutTile
                            icon={<KeyRound size={13} aria-hidden="true" />}
                            label={t("administration.permissions.label")}
                            value={permissionCatalog.data?.length}
                            isLoading={permissionCatalog.isLoading}
                            isError={permissionCatalog.isError}
                            secondary={t("administration.permissions.secondary", { count: resourceTypes ?? 0 })}
                            onClick={() => navigate("/permissions")}
                        />
                    )}
                    {canRateLimits && (
                        <OperationShortcutTile
                            icon={<Gauge size={13} aria-hidden="true" />}
                            label={t("administration.rateLimits.label")}
                            value={rateLimits.data}
                            isLoading={rateLimits.isLoading}
                            isError={rateLimits.isError}
                            secondary={t("administration.rateLimits.secondary")}
                            onClick={() => navigate("/rate-limits")}
                        />
                    )}
                    {canSecurityAudit && (
                        <OperationShortcutTile
                            icon={<Shield size={13} aria-hidden="true" />}
                            label={t("administration.securityEvents.label")}
                            secondary={t("administration.securityEvents.secondary")}
                            onClick={() => navigate("/audit-log?category=security&scope=all")}
                        />
                    )}
                </div>
            </div>
        </Card>
    );
};

export default OperationsShortcutsCard;
