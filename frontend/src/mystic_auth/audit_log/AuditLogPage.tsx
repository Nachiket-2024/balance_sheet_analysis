import React from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../ui/shadcn/tabs";
import { ScrollText } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import PageContainer from "../ui/navigation/PageContainer";
import { IfCan } from "../authorization/IfCan";
import { useCan } from "../authorization/useCan";
import { PERMISSIONS } from "../authorization/permissions";
import MyAuthorizationLogSection from "./authorization_log/MyAuthorizationLogSection";
import AllAuthorizationLogSection from "./authorization_log/AllAuthorizationLogSection";
import MySecurityLogSection from "./security_log/MySecurityLogSection";
import AllSecurityLogSection from "./security_log/AllSecurityLogSection";
import { useAuditLogUiStore } from "./auditLogUiStore";

/**
 * AuditLogPage
 * ----------------------------
 * Every authenticated user can see their own authorization-decision and security-event
 * history (backend: GET /authorization/audit-log/me, GET /audit/security-log/me, auth-only).
 * A caller who also holds policies:read / security_audit:read gets an "All users" tab for
 * that log, backed by the matching management endpoint. The route itself needs no permission:
 * each tab decides its own access via IfCan, mirroring how the backend splits self vs.
 * management visibility across these four endpoints.
 *
 * Category (Authorization decisions vs. Security events) and scope (My activity vs. All
 * users) are two independent tab bars rather than both log types stacked on one page: only
 * one table renders at a time. Every table pages via numbered Pagination, sorts server-side
 * by column header, and narrows further via a filter bar; all page/filter state lives
 * client-side while the data stays server-side, so none of this depends on log size.
 *
 * Split by section into two subfolders matching the two tabs: authorization_log/
 * (MyAuthorizationLogSection, AllAuthorizationLogSection, AuthorizationFilterBar, and its own
 * columns/queries/resourceTypes files) and security_log/ (the same set, plus
 * LoginTrendChart.tsx). What's identical across both tabs lives here instead:
 * auditLogListConfig.ts (PAGE_SIZE/formatTimestamp/etc.) and auditLogPageResult.ts
 * (X-Total-Count -> {rows,total} parsing). This file is just the tab shell.
 */
interface AuditLogPageProps {
    /**
     * Resource types/actions beyond this app's own PBAC vocabulary (authorizationLogResourceTypes.ts /
     * permissions.ts), for downstream projects that extend PBAC for their own domain. Same
     * pattern as AppLayout's extraNavItems: additive, optional, no-op when omitted.
     * See docs/mystic_auth/template-usage/frontend-customization.md#shared-chrome-extension-points.
     */
    extraResourceTypes?: string[];
    extraActions?: string[];
}

/** "All users" tab trigger. It is omitted entirely when the caller lacks the
 * management permission, so the tab bar only presents destinations the user
 * can actually open. Backend authorization remains the source of truth. */
const AllUsersTabTrigger: React.FC<{ permission: string; label: string }> = ({
    permission, label,
}) => {
    const allowed = useCan(permission);
    return allowed ? <TabsTrigger value="all" className="relative z-30 !h-9 !min-h-9 pointer-events-auto text-base">{label}</TabsTrigger> : null;
};

const AuditLogPage: React.FC<AuditLogPageProps> = ({ extraResourceTypes, extraActions }) => {
    const { t } = useTranslation("audit_log");
    const canReadAllPolicies = useCan(PERMISSIONS.POLICIES_READ);
    const canReadAllSecurity = useCan(PERMISSIONS.SECURITY_AUDIT_READ);

    // Precedence, same as AccountSettingsPage's activeTab: `?category=`/`?scope=` are
    // one-shot deep-link overrides (CommandPalette's content-search results, see
    // layout/command_palette/searchItems.ts, navigate to e.g.
    // /audit-log?category=security&scope=all to land on a specific category+scope pair),
    // then auditLogUiStore's last-used values (so leaving this page and coming back
    // reopens on the same category/scope instead of resetting), then the hardcoded
    // defaults. `scope` means the same thing in both category branches (each has its own
    // inner Tabs), so it's one store field/one URL param rather than per-branch.
    const [searchParams, setSearchParams] = useSearchParams();
    const storedCategory = useAuditLogUiStore((s) => s.category);
    const storedScope = useAuditLogUiStore((s) => s.scope);
    const setStored = useAuditLogUiStore((s) => s.update);
    const initialCategory = searchParams.get("category") ?? storedCategory ?? "authorization";
    const requestedScope = searchParams.get("scope") ?? storedScope ?? "mine";
    const initialScope = requestedScope !== "all"
        || (initialCategory === "authorization" ? canReadAllPolicies : canReadAllSecurity)
        ? requestedScope
        : "mine";
    const activeCategoryLabel = initialCategory === "security"
        ? t("tabs.securityEvents")
        : t("tabs.authorizationDecisions");
    const activeScopeLabel = initialScope === "all"
        ? t("tabs.allUsers")
        : t("tabs.myActivity");

    // Written back to the URL (not just the store) on every change, so a refresh or a shared
    // link lands back on the same category/scope instead of only the store's last-used value.
    const setCategory = (value: string) => {
        setStored({ category: value });
        setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.set("category", value);
            return next;
        }, { replace: true });
    };
    const setScope = (value: string) => {
        setStored({ scope: value });
        setSearchParams((prev) => {
            const next = new URLSearchParams(prev);
            next.set("scope", value);
            return next;
        }, { replace: true });
    };

    return (
        <PageContainer title={t("page.title")} icon={ScrollText} description={t("page.description")}>
            <div
                className="sr-only"
                aria-live="polite"
                aria-atomic="true"
                data-testid="audit-log-view-summary"
            >
                <span className="text-fg-muted">{activeCategoryLabel}</span>
                <span aria-hidden="true" className="text-fg-muted">/</span>
                <span className="font-semibold text-fg-default">{activeScopeLabel}</span>
            </div>
            <Tabs
                key={initialCategory}
                defaultValue={initialCategory}
                className="mb-4"
                onValueChange={setCategory}
            >
                <TabsList variant="line" aria-label={t("page.title")}>
                    <TabsTrigger value="authorization" className="text-base">{t("tabs.authorizationDecisions")}</TabsTrigger>
                    <TabsTrigger value="security" className="text-base">{t("tabs.securityEvents")}</TabsTrigger>
                </TabsList>

                    <TabsContent value="authorization">
                        <Tabs key={initialScope} defaultValue={initialScope} onValueChange={setScope} className="relative z-20">
                        <TabsList
                            variant="line"
                            className="relative z-20 h-9"
                            aria-label={t("tabs.authorizationDecisions")}
                        >
                            <TabsTrigger value="mine" className="relative z-30 !h-9 !min-h-9 pointer-events-auto text-base">{t("tabs.myActivity")}</TabsTrigger>
                            <AllUsersTabTrigger
                                permission={PERMISSIONS.POLICIES_READ}
                                label={t("tabs.allUsers")}
                            />
                        </TabsList>
                        <TabsContent value="mine">
                            <MyAuthorizationLogSection
                                extraResourceTypes={extraResourceTypes}
                                extraActions={extraActions}
                            />
                        </TabsContent>
                        <IfCan action={PERMISSIONS.POLICIES_READ}>
                            <TabsContent value="all">
                                <AllAuthorizationLogSection
                                    extraResourceTypes={extraResourceTypes}
                                    extraActions={extraActions}
                                />
                            </TabsContent>
                        </IfCan>
                    </Tabs>
                </TabsContent>

                    <TabsContent value="security">
                        <Tabs key={initialScope} defaultValue={initialScope} onValueChange={setScope} className="relative z-20">
                        <TabsList
                            variant="line"
                            className="relative z-20 h-9"
                            aria-label={t("tabs.securityEvents")}
                        >
                            <TabsTrigger value="mine" className="relative z-30 !h-9 !min-h-9 pointer-events-auto text-base">{t("tabs.myActivity")}</TabsTrigger>
                            <AllUsersTabTrigger
                                permission={PERMISSIONS.SECURITY_AUDIT_READ}
                                label={t("tabs.allUsers")}
                            />
                        </TabsList>
                        <TabsContent value="mine">
                            <MySecurityLogSection />
                        </TabsContent>
                        <IfCan action={PERMISSIONS.SECURITY_AUDIT_READ}>
                            <TabsContent value="all">
                                <AllSecurityLogSection />
                            </TabsContent>
                        </IfCan>
                    </Tabs>
                </TabsContent>
            </Tabs>
        </PageContainer>
    );
};

export default AuditLogPage;
