import React from "react";
import { Tabs } from "@chakra-ui/react";

import PageContainer from "../ui/PageContainer";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import MyAuthorizationLogSection from "./authorization_log/MyAuthorizationLogSection";
import AllAuthorizationLogSection from "./authorization_log/AllAuthorizationLogSection";
import MySecurityLogSection from "./security_log/MySecurityLogSection";
import AllSecurityLogSection from "./security_log/AllSecurityLogSection";

/**
 * AuditLogPage
 * ----------------------------
 * Every authenticated user can see their own authorization-decision and
 * security-event history (backend: GET /authorization/audit-log/me,
 * GET /audit/security-log/me, auth-only, no extra permission). A caller
 * who additionally holds policies:read / security_audit:read also sees an
 * "All users" tab for that log, backed by the corresponding management endpoint.
 * The route itself carries no permission requirement: access to each tab
 * is decided per-tab via IfCan, mirroring exactly how the backend splits
 * self vs. management visibility across these four endpoints.
 *
 * Category (Authorization decisions vs. Security events) and scope (My
 * activity vs. All users) are two independent tab bars rather than one
 * page with both log types stacked full-height one after another: only one
 * table renders at a time, so opening the page doesn't dump two full
 * tables' worth of scroll on you before you've picked what you came to
 * look at. Every table pages via numbered Pagination (shown above and
 * below) rather than growing downward, every column header sorts the
 * whole result set server-side, and a filter bar (select/text controls,
 * not free-typed sort) narrows it further - all three compose together and
 * all page/reset state lives client-side while the actual data stays
 * server-side, so none of this depends on how many rows the log has grown to.
 *
 * Split across files by section, grouped into two subfolders matching the
 * two tabs - everything specific to just one tab lives inside it:
 * authorization_log/ (MyAuthorizationLogSection, AllAuthorizationLogSection,
 * AuthorizationFilterBar, its own authorizationLogColumns.tsx/authorizationLogQueries.ts/authorizationLogResourceTypes.ts)
 * and security_log/ (MySecurityLogSection, AllSecurityLogSection,
 * SecurityFilterBar, its own securityLogColumns.tsx/securityLogQueries.ts/securityLogEventTypes.ts, plus
 * LoginTrendChart.tsx). What's genuinely identical for both tabs stays here
 * instead of being duplicated into each: auditLogListConfig.ts
 * (PAGE_SIZE/formatTimestamp/etc.) and auditLogPageResult.ts
 * (X-Total-Count -> {rows,total} parsing, shared by both queries.ts files).
 * This file is just the tab shell composing it all, not the ~500-line
 * single file this used to be.
 */
const AuditLogPage: React.FC = () => {
    return (
        <PageContainer title="Audit Log" description="Authorization decisions and security events.">
            <Tabs.Root defaultValue="authorization" mb={4} lazyMount unmountOnExit>
                <Tabs.List>
                    <Tabs.Trigger value="authorization" fontSize="15px">Authorization decisions</Tabs.Trigger>
                    <Tabs.Trigger value="security" fontSize="15px">Security events</Tabs.Trigger>
                </Tabs.List>

                <Tabs.Content value="authorization">
                    <Tabs.Root defaultValue="mine" lazyMount unmountOnExit>
                        <Tabs.List>
                            <Tabs.Trigger value="mine" fontSize="15px">My activity</Tabs.Trigger>
                            <IfCan action={PERMISSIONS.POLICIES_READ}>
                                <Tabs.Trigger value="all" fontSize="15px">All users</Tabs.Trigger>
                            </IfCan>
                        </Tabs.List>
                        <Tabs.Content value="mine">
                            <MyAuthorizationLogSection />
                        </Tabs.Content>
                        <IfCan action={PERMISSIONS.POLICIES_READ}>
                            <Tabs.Content value="all">
                                <AllAuthorizationLogSection />
                            </Tabs.Content>
                        </IfCan>
                    </Tabs.Root>
                </Tabs.Content>

                <Tabs.Content value="security">
                    <Tabs.Root defaultValue="mine" lazyMount unmountOnExit>
                        <Tabs.List>
                            <Tabs.Trigger value="mine" fontSize="15px">My activity</Tabs.Trigger>
                            <IfCan action={PERMISSIONS.SECURITY_AUDIT_READ}>
                                <Tabs.Trigger value="all" fontSize="15px">All users</Tabs.Trigger>
                            </IfCan>
                        </Tabs.List>
                        <Tabs.Content value="mine">
                            <MySecurityLogSection />
                        </Tabs.Content>
                        <IfCan action={PERMISSIONS.SECURITY_AUDIT_READ}>
                            <Tabs.Content value="all">
                                <AllSecurityLogSection />
                            </Tabs.Content>
                        </IfCan>
                    </Tabs.Root>
                </Tabs.Content>
            </Tabs.Root>
        </PageContainer>
    );
};

export default AuditLogPage;
