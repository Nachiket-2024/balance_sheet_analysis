import React from "react";
import { Badge, Tabs, Text } from "@chakra-ui/react";

import PageContainer from "../ui/PageContainer";
import DataTable, { type DataTableColumn } from "../ui/DataTable";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import {
    useMyAuthorizationAuditLogQuery,
    useAuthorizationAuditLogQuery,
    useMySecurityAuditLogQuery,
    useSecurityAuditLogQuery,
} from "./auditQueries";
import type { AuthorizationAuditLogEntryRead, SecurityAuditLogEntryRead } from "../api/audit_api";

function formatTimestamp(iso: string): string {
    return new Date(iso).toLocaleString();
}

const authorizationColumns: DataTableColumn<AuthorizationAuditLogEntryRead>[] = [
    { key: "created_at", header: "When", render: (e) => formatTimestamp(e.created_at) },
    { key: "user_email", header: "User", render: (e) => e.user_email },
    { key: "action", header: "Action", render: (e) => e.action },
    { key: "resource_type", header: "Resource", render: (e) => e.resource_type },
    {
        key: "allowed",
        header: "Result",
        render: (e) => (
            <Badge colorPalette={e.allowed ? "green" : "red"}>{e.allowed ? "Allowed" : "Denied"}</Badge>
        ),
    },
];

const securityColumns: DataTableColumn<SecurityAuditLogEntryRead>[] = [
    { key: "created_at", header: "When", render: (e) => formatTimestamp(e.created_at) },
    { key: "user_email", header: "User", render: (e) => e.user_email ?? ":" },
    { key: "event_type", header: "Event", render: (e) => e.event_type },
    { key: "ip_address", header: "IP", render: (e) => e.ip_address ?? ":" },
    {
        key: "success",
        header: "Result",
        render: (e) => <Badge colorPalette={e.success ? "green" : "red"}>{e.success ? "Success" : "Failed"}</Badge>,
    },
];

const MyAuthorizationLog: React.FC = () => {
    const { data, isLoading, isError } = useMyAuthorizationAuditLogQuery();
    return (
        <DataTable
            columns={authorizationColumns}
            rows={data}
            rowKey={(e) => e.id}
            isLoading={isLoading}
            isError={isError}
            emptyMessage="No authorization decisions recorded yet"
        />
    );
};

const AllAuthorizationLog: React.FC = () => {
    const { data, isLoading, isError } = useAuthorizationAuditLogQuery();
    return (
        <DataTable
            columns={authorizationColumns}
            rows={data}
            rowKey={(e) => e.id}
            isLoading={isLoading}
            isError={isError}
            emptyMessage="No authorization decisions recorded yet"
        />
    );
};

const MySecurityLog: React.FC = () => {
    const { data, isLoading, isError } = useMySecurityAuditLogQuery();
    return (
        <DataTable
            columns={securityColumns}
            rows={data}
            rowKey={(e) => e.id}
            isLoading={isLoading}
            isError={isError}
            emptyMessage="No security events recorded yet"
        />
    );
};

const AllSecurityLog: React.FC = () => {
    const { data, isLoading, isError } = useSecurityAuditLogQuery();
    return (
        <DataTable
            columns={securityColumns}
            rows={data}
            rowKey={(e) => e.id}
            isLoading={isLoading}
            isError={isError}
            emptyMessage="No security events recorded yet"
        />
    );
};

/**
 * AuditLogPage
 * ----------------------------
 * Every authenticated user can see their own authorization-decision and
 * security-event history (backend: GET /authorization/audit-log/me,
 * GET /audit/security-log/me, auth-only, no extra permission). A caller
 * who additionally holds policies:read / security_audit:read also sees an
 * "All users" tab for that log, backed by the corresponding admin endpoint.
 * The route itself carries no permission requirement: access to each tab
 * is decided per-tab via IfCan, mirroring exactly how the backend splits
 * self vs. admin visibility across these four endpoints.
 */
const AuditLogPage: React.FC = () => {
    return (
        <PageContainer title="Audit Log" description="Authorization decisions and security events.">
            <Text fontWeight="semibold" mb={2}>
                Authorization decisions
            </Text>
            <Tabs.Root defaultValue="mine" mb={8}>
                <Tabs.List>
                    <Tabs.Trigger value="mine">My activity</Tabs.Trigger>
                    <IfCan action={PERMISSIONS.POLICIES_READ}>
                        <Tabs.Trigger value="all">All users</Tabs.Trigger>
                    </IfCan>
                </Tabs.List>
                <Tabs.Content value="mine">
                    <MyAuthorizationLog />
                </Tabs.Content>
                <IfCan action={PERMISSIONS.POLICIES_READ}>
                    <Tabs.Content value="all">
                        <AllAuthorizationLog />
                    </Tabs.Content>
                </IfCan>
            </Tabs.Root>

            <Text fontWeight="semibold" mb={2}>
                Security events
            </Text>
            <Tabs.Root defaultValue="mine">
                <Tabs.List>
                    <Tabs.Trigger value="mine">My activity</Tabs.Trigger>
                    <IfCan action={PERMISSIONS.SECURITY_AUDIT_READ}>
                        <Tabs.Trigger value="all">All users</Tabs.Trigger>
                    </IfCan>
                </Tabs.List>
                <Tabs.Content value="mine">
                    <MySecurityLog />
                </Tabs.Content>
                <IfCan action={PERMISSIONS.SECURITY_AUDIT_READ}>
                    <Tabs.Content value="all">
                        <AllSecurityLog />
                    </Tabs.Content>
                </IfCan>
            </Tabs.Root>
        </PageContainer>
    );
};

export default AuditLogPage;
